// MORM Phase 22-Video — browser-to-browser HLS segment mesh via WebRTC.
//
// Spec ref: PHASE25-VIDEO.md §9 — "Phase 22/22b (P2P + TURN): WebRTC で配信する
// binary を `.cell` から `.m4s` に変更。チャンクサイズと chunked transfer は変わらない".
// MORM.md §2/§3 — "Light Node が余剰リソースで他者の3秒を中継する".
//
// Each browser tab:
//   - announces (peer_id, content_id, segments_held) every 5s to the gateway
//     where segments_held is a list of HLS segment ids like
//     "1080p/seg_1.m4s" or "720p/init_3.mp4"
//   - on a segment miss: queries `/api/signal/peers/{cid}` for other tabs that
//     hold that segment, opens a DataChannel to one of them, and pulls it
//   - on the serving side: holds an open RTCPeerConnection per requester,
//     reads the segment bytes from the HTTP cache and writes them to the
//     channel
//
// Signaling is a tiny mailbox at the gateway; once the DataChannel is open,
// segment bytes flow peer-to-peer (no server bandwidth cost).
//
// Wire compatibility: the gateway's signaling layer treats the announced list
// as opaque strings (`payload["cells"]` is a back-compat field name), so
// nothing changes server-side when we switch from int indices to "ladder/name".

const SIGNAL_BASE  = '';                 // same origin as the gateway
const FALLBACK_ICE = [{ urls: 'stun:stun.l.google.com:19302' }];
const ANNOUNCE_INTERVAL_MS = 5000;
// Mailbox poll interval. 200ms is fast enough that offer/answer/ICE
// roundtrips complete in ~1s end-to-end (the gateway is in-process and
// signaling round-trips dominate handshake latency). Lower than this and
// hidden / backgrounded frames see no benefit due to Chrome's intersection-
// observer throttling at >1s intervals.
const POLL_INTERVAL_MS     = 200;
const ICE_REFRESH_MS       = 5 * 60 * 1000;   // ephemeral TURN creds expire

let ICE_SERVERS = FALLBACK_ICE.slice();
let iceLoaded   = false;

const peerId = (() => {
  // Allow ?morm-peer=<id> URL override so multi-iframe / multi-tab dev tests
  // can mint distinct peer ids without sessionStorage collisions (sibling
  // same-origin iframes share sessionStorage with the parent doc).
  const m = location.search.match(/[?&]morm-peer=([0-9a-fA-F]+)/);
  if (m) return m[1];
  let id = sessionStorage.getItem('morm-peer-id');
  if (!id) {
    id = [...crypto.getRandomValues(new Uint8Array(8))]
         .map(b => b.toString(16).padStart(2, '0')).join('');
    sessionStorage.setItem('morm-peer-id', id);
  }
  return id;
})();

async function loadIceConfig() {
  try {
    const r = await fetch(`${SIGNAL_BASE}/api/signal/ice?peer_id=${peerId}`);
    if (!r.ok) throw new Error('ice fetch ' + r.status);
    const j = await r.json();
    if (Array.isArray(j.ice_servers) && j.ice_servers.length) {
      ICE_SERVERS = j.ice_servers;
      iceLoaded = true;
      const hasTurn = ICE_SERVERS.some(s => {
        const u = Array.isArray(s.urls) ? s.urls : [s.urls];
        return u.some(x => typeof x === 'string' && x.startsWith('turn'));
      });
      stat.iceMode = hasTurn ? 'turn' : 'stun';
    }
  } catch (e) {
    console.warn('ice config fetch failed; using STUN fallback', e);
    stat.iceMode = 'stun-fallback';
  }
}
const iceReady = loadIceConfig();
setInterval(loadIceConfig, ICE_REFRESH_MS);

const stat = {
  p2pHits: 0, p2pBytes: 0, peerCount: 0, iceMode: 'loading',
  // Phase 26q — count how many P2P responses we threw away because the
  // bytes didn't hash to the vhash baked into the filename. A non-zero
  // value here means at least one peer is serving poisoned content (or a
  // bug in segment naming on the encoder side).
  p2pRejects: 0,
};
let currentContentId = null;
let segmentsHeld = new Set();           // Set<string> of "ladder/name" ids
const incomingPCs  = new Map();    // peer_id -> RTCPeerConnection (serving)
const outgoingPCs  = new Map();    // peer_id -> RTCPeerConnection (fetching)
const pendingFetch = new Map();    // request_id -> {resolve, reject, peer_id}

// HLS segment URL on the same origin gateway. Mirrors _serve_hls in
// passkey_morm.py, which routes /api/video/<cid>/<ladder>/<filename>.
const segmentUrl = (cid, segId) => `/api/video/${cid}/${segId}`;
// MIME for HLS init.mp4 vs .m4s — the gateway returns these but we re-build
// Response objects in the cache, so we must set the type ourselves.
const segmentMime = (segId) =>
  segId.endsWith('.mp4') ? 'video/mp4' : 'video/iso.segment';

// Phase 26q — content verification.
//
// HLS encoder names .m4s segments `seg_NNNNN.<vhash16>.m4s` where vhash16 is
// the first 16 hex chars of sha256(bytes) (see morm-core/hls_encoder.py
// :_rewrite_segments_with_vhash). That makes the filename a self-contained
// content commitment: any tampering by an upstream peer changes the bytes
// → changes the hash → no longer matches the path the player asked for.
//
// init.mp4 is named `init_<varindex>.mp4` and its hash lives in
// manifest.json (init_hashes), NOT the filename. Verifying it from the
// filename alone is impossible, so for now we keep init.mp4 OUT of the
// P2P path (fetched from origin only). The init blob is ~1 KB and loaded
// once per content, so the bandwidth cost of skipping P2P is negligible.
const _VHASH_RE = /\.([0-9a-f]{16})\.m4s$/;
function _vhashFromSegId(segId) {
  const m = _VHASH_RE.exec(segId || '');
  return m ? m[1] : null;
}
async function _sha256Hex16(arrayBuf) {
  const digest = await crypto.subtle.digest('SHA-256', arrayBuf);
  let hex = '';
  for (const b of new Uint8Array(digest, 0, 8)) {
    hex += b.toString(16).padStart(2, '0');
  }
  return hex;
}
async function _verifyBlobAgainstSegId(blob, segId) {
  const expected = _vhashFromSegId(segId);
  if (!expected) return false;     // not a verifiable .m4s — caller decides
  const buf = await blob.arrayBuffer();
  const got = await _sha256Hex16(buf);
  return got === expected;
}

// ---- public API used by player-hls.js -----------------------------------
export function p2pStats() { return { ...stat, peer_id: peerId }; }
export function setP2PContent(content_id) {
  currentContentId = content_id;
  segmentsHeld = new Set();
  scheduleAnnounce();
}
export function rememberSegment(content_id, seg_id) {
  if (currentContentId === content_id) {
    segmentsHeld.add(seg_id);
    scheduleAnnounce();    // re-announce so peers see we just gained a segment
  }
}

/**
 * Try to fetch (cid, seg_id) from any peer that announced it. Resolves with a
 * Blob, or null if no peer or all attempts failed. seg_id is a string of the
 * form "1080p/seg_1.m4s" or "1080p/init_3.mp4".
 *
 * Phase 26q content verification: only `.m4s` segments are pulled via P2P,
 * because their vhash is in the filename (self-verifying). init.mp4 always
 * falls through to origin — its hash lives in manifest.json, which we
 * don't currently fetch, and the file is small so the egress cost is
 * trivial. After receiving bytes, we recompute sha256[:16] and compare to
 * the vhash baked into the filename; on mismatch we drop the bytes,
 * increment p2pRejects, and try the next candidate.
 */
export async function p2pTryFetchSegment(content_id, seg_id, timeoutMs = 4000) {
  if (content_id !== currentContentId) return null;
  // Phase 26q — only verifiable seg_ids enter the P2P path.
  if (!_vhashFromSegId(seg_id)) return null;
  await iceReady;     // make sure first ICE config attempt finished
  const peers = await listPeers(content_id);
  const candidates = peers.filter(p =>
    p.peer_id !== peerId && Array.isArray(p.cells) && p.cells.includes(seg_id));
  if (!candidates.length) return null;
  for (const p of candidates) {
    try {
      const blob = await requestSegmentFromPeer(p.peer_id, content_id, seg_id, timeoutMs);
      if (!blob || blob.size === 0) continue;
      // Phase 26q — refuse anything that doesn't hash to the filename's
      // vhash. We do NOT cache the bad bytes, do NOT rememberSegment, and
      // do NOT count it as a P2P hit.
      const ok = await _verifyBlobAgainstSegId(blob, seg_id);
      if (!ok) {
        stat.p2pRejects += 1;
        console.warn('p2p reject (vhash mismatch)', p.peer_id, seg_id);
        continue;
      }
      stat.p2pHits  += 1;
      stat.p2pBytes += blob.size;
      rememberSegment(content_id, seg_id);     // we now hold it too
      // Write into the HTTP cache so subsequent SW / hls.js requests are
      // local. Cache key matches _serve_hls origin URL exactly.
      try {
        const cache = await caches.open('morm-hls-v1');
        await cache.put(segmentUrl(content_id, seg_id),
          new Response(blob, { headers: {
            'Content-Type': segmentMime(seg_id),
            'Cache-Control': 'public, max-age=31536000, immutable',
            'X-MORM-P2P': 'hit',
          }}));
      } catch {}
      return blob;
    } catch (e) {
      console.warn('p2p attempt failed', p.peer_id, e);
    }
  }
  return null;
}

// ---- announce loop ------------------------------------------------------
let announceTimer = null;
function scheduleAnnounce() {
  if (announceTimer) clearTimeout(announceTimer);
  announceTimer = setTimeout(announce, 100);
}
async function announce() {
  if (!currentContentId) return;
  try {
    await fetch(`${SIGNAL_BASE}/api/signal/announce`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        peer_id: peerId,
        content_id: currentContentId,
        // Server-side field name is "cells" for back-compat with Phase 22
        // (.webm cell era); we ship the segment id strings directly through
        // the same opaque slot.
        cells: [...segmentsHeld].sort(),
      }),
    });
  } catch {}
}
setInterval(announce, ANNOUNCE_INTERVAL_MS);

async function listPeers(cid) {
  const r = await fetch(`${SIGNAL_BASE}/api/signal/peers/${cid}?exclude=${peerId}`);
  const j = await r.json();
  stat.peerCount = j.peers.length;
  return j.peers;
}

// ---- mailbox poll for signaling messages --------------------------------
// IMPORTANT: handleSignal must run SEQUENTIALLY. The offer handler awaits
// setRemoteDescription / createAnswer; if we dispatched ICE handlers in
// parallel they'd race the offer handler and call addIceCandidate before
// the remote description is set, silently dropping every candidate. With
// `await` here, ICE candidates from the same poll batch only run after
// the offer handler has fully completed and the PC is ready to accept them.
setInterval(async () => {
  try {
    const r = await fetch(`${SIGNAL_BASE}/api/signal/inbox/${peerId}`);
    const j = await r.json();
    for (const m of j.messages || []) {
      try { await handleSignal(m); } catch (e) { console.warn('handleSignal', e); }
    }
  } catch {}
}, POLL_INTERVAL_MS);

async function sendSignal(to, kind, data) {
  await fetch(`${SIGNAL_BASE}/api/signal/send`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ from: peerId, to, kind, data }),
  });
}

const P2P_DEBUG = /[?&]p2p-debug/.test(location.search);
const dlog = (...a) => { if (P2P_DEBUG) console.log('[p2p]', peerId.slice(0,4), ...a); };

async function handleSignal(msg) {
  const { from, kind, data } = msg;
  dlog('signal in', kind, 'from', from.slice(0,4));
  if (kind === 'offer') {
    await iceReady;   // ensure TURN creds are loaded before accepting offers
    // we're the server side (we hold the segment). Answer + open serving DC.
    const pc = new RTCPeerConnection({ iceServers: ICE_SERVERS });
    incomingPCs.set(from, pc);
    pc.ondatachannel = ev => { dlog('serving DC opened'); attachServingChannel(ev.channel); };
    pc.onconnectionstatechange = () => dlog('serving pc state', pc.connectionState);
    pc.oniceconnectionstatechange = () => dlog('serving ice state', pc.iceConnectionState);
    pc.onicecandidate = e => {
      if (e.candidate) sendSignal(from, 'ice', e.candidate.toJSON());
    };
    await pc.setRemoteDescription({ type: 'offer', sdp: data });
    const answer = await pc.createAnswer();
    await pc.setLocalDescription(answer);
    sendSignal(from, 'answer', answer.sdp);
  } else if (kind === 'answer') {
    const pc = outgoingPCs.get(from);
    if (pc && pc.signalingState !== 'stable')
      await pc.setRemoteDescription({ type: 'answer', sdp: data });
  } else if (kind === 'ice') {
    const pc = outgoingPCs.get(from) || incomingPCs.get(from);
    if (pc && data) {
      try { await pc.addIceCandidate(data); } catch {}
    }
  }
}

// Drop a stuck/closed PC so the next fetch attempt forces a fresh
// handshake. Without this, a single failed offer leaves outgoingPCs
// holding a dead reference forever (the most common P2P bug in this code:
// see Phase 22-Video debug session 2026-04-29).
function dropOutgoing(peer_id) {
  const pc = outgoingPCs.get(peer_id);
  if (pc) { try { pc.close(); } catch {} }
  outgoingPCs.delete(peer_id);
  outgoingDC.delete(peer_id);
}

// ---- requesting side ----------------------------------------------------
function requestSegmentFromPeer(peer_id, cid, seg_id, timeoutMs) {
  return new Promise(async (resolve, reject) => {
    const reqId = [...crypto.getRandomValues(new Uint8Array(6))]
      .map(b => b.toString(16).padStart(2, '0')).join('');
    let pc = outgoingPCs.get(peer_id);
    // Recycle broken PCs from prior attempts. connectionState transitions
    // to "failed" / "closed" / "disconnected" on ICE failure or remote
    // teardown; the cached signalingState may also stick on
    // "have-local-offer" if the answer never arrived.
    if (pc && (pc.connectionState === 'failed'
            || pc.connectionState === 'closed'
            || pc.connectionState === 'disconnected'
            || pc.iceConnectionState === 'failed'
            || pc.iceConnectionState === 'disconnected')) {
      dropOutgoing(peer_id);
      pc = null;
    }
    if (!pc) {
      pc = new RTCPeerConnection({ iceServers: ICE_SERVERS });
      outgoingPCs.set(peer_id, pc);
      pc.onicecandidate = e => {
        if (e.candidate) sendSignal(peer_id, 'ice', e.candidate.toJSON());
      };
      pc.onconnectionstatechange = () => {
        if (pc.connectionState === 'failed' || pc.connectionState === 'closed') {
          dropOutgoing(peer_id);
        }
      };
      const dc = pc.createDataChannel('morm', { ordered: true });
      attachFetchingChannel(dc, peer_id);
      const offer = await pc.createOffer();
      await pc.setLocalDescription(offer);
      await sendSignal(peer_id, 'offer', offer.sdp);
    }
    pendingFetch.set(reqId, { resolve, reject, peer_id, seg_id });
    setTimeout(() => {
      if (pendingFetch.has(reqId)) {
        pendingFetch.delete(reqId);
        // Drop the PC on timeout — the most likely cause is that the
        // remote never answered (offer lost, or remote dropped). A fresh
        // handshake on retry has a much better chance.
        dropOutgoing(peer_id);
        reject(new Error('p2p timeout'));
      }
    }, timeoutMs);
    // wait for DataChannel to open before sending the request
    const t0 = Date.now();
    const trySend = () => {
      const dc = outgoingDC.get(peer_id);
      if (dc && dc.readyState === 'open') {
        dc.send(JSON.stringify({ kind: 'segment-request', req_id: reqId, cid, seg_id }));
      } else if (Date.now() - t0 < timeoutMs) {
        setTimeout(trySend, 100);
      }
      // else: outer timeout setTimeout will reject + drop the PC
    };
    trySend();
  });
}

const outgoingDC = new Map();
function attachFetchingChannel(dc, peer_id) {
  dc.binaryType = 'arraybuffer';
  let pendingReqId = null;
  let receiveBuffer = [];
  let receiveTotal = 0;
  let expectedSize = 0;
  dc.onopen = () => {
    dlog('fetching DC opened to', peer_id.slice(0,4));
    outgoingDC.set(peer_id, dc);
  };
  dc.onerror = e => dlog('fetching DC error', e?.message || e);
  dc.onclose = () => dlog('fetching DC closed');
  dc.onmessage = ev => {
    if (typeof ev.data === 'string') {
      const msg = JSON.parse(ev.data);
      if (msg.kind === 'segment-header') {
        pendingReqId = msg.req_id;
        receiveBuffer = [];
        receiveTotal = 0;
        expectedSize = msg.size;
      } else if (msg.kind === 'segment-error') {
        const p = pendingFetch.get(msg.req_id);
        if (p) { pendingFetch.delete(msg.req_id); p.reject(new Error(msg.error)); }
      }
    } else {
      receiveBuffer.push(new Uint8Array(ev.data));
      receiveTotal += ev.data.byteLength;
      if (receiveTotal >= expectedSize && pendingReqId) {
        const p = pendingFetch.get(pendingReqId);
        const segId = p?.seg_id || '';
        const blob = new Blob(receiveBuffer, { type: segmentMime(segId) });
        if (p) { pendingFetch.delete(pendingReqId); p.resolve(blob); }
        pendingReqId = null;
        receiveBuffer = [];
      }
    }
  };
}

// ---- serving side -------------------------------------------------------
function attachServingChannel(dc) {
  dc.binaryType = 'arraybuffer';
  dc.onmessage = async ev => {
    if (typeof ev.data !== 'string') return;
    let msg;
    try { msg = JSON.parse(ev.data); } catch { return; }
    if (msg.kind !== 'segment-request') return;
    const { req_id, cid, seg_id } = msg;
    try {
      // Look up the segment in any cache we own. Prefer the dedicated
      // morm-hls-v1 store (where p2pTryFetchSegment writes hits), then
      // fall through to whatever the SW or browser has cached on the same
      // origin URL.
      let cached = null;
      try {
        const cache = await caches.open('morm-hls-v1');
        cached = await cache.match(segmentUrl(cid, seg_id));
      } catch {}
      if (!cached) {
        cached = await caches.match(segmentUrl(cid, seg_id));
      }
      if (!cached) {
        dc.send(JSON.stringify({ kind: 'segment-error', req_id, error: 'not in cache' }));
        return;
      }
      const buf = await cached.arrayBuffer();
      dc.send(JSON.stringify({ kind: 'segment-header', req_id, size: buf.byteLength }));
      // chunk: WebRTC DataChannel safe single-message size is ~16KB
      const CHUNK = 16 * 1024;
      for (let off = 0; off < buf.byteLength; off += CHUNK) {
        dc.send(buf.slice(off, Math.min(off + CHUNK, buf.byteLength)));
      }
    } catch (e) {
      dc.send(JSON.stringify({ kind: 'segment-error', req_id, error: String(e) }));
    }
  };
}
