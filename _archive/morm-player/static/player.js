// MORM 50/10 cycle player — multi-edge swarm fetcher.
//
// Peer edges live at the URLs in `EDGES` below. For every cell fetch we pick
// a random peer; on failure we fall through the rest. Each successful fetch
// records a hit on that peer (HUD chart). Cell decoding uses the same
// dual-buffer 50/10 scheme as Phase 3.
//
// Phase 11d: when a viewer has a MORM Identity (registered via the passkey
// gateway), each unique cell view fires a passkey-gated view_reward tx to
// MORM Chain L1 — the "Pulse" the design book describes, but actually
// settled on-chain.

import { listIdentities, claimViewReward } from '/static/morm-identity.js';
import {
  p2pStats, setP2PContent,
  p2pTryFetchSegment, rememberSegment,
} from '/static/morm-p2p.js';
// Phase 22-Video: P2P module switched from .cell ints to HLS segment-id
// strings. The legacy WebM swarm player below adapts by stringifying the
// integer cell index — the gateway's signaling layer treats it as opaque.
const p2pTryFetch  = (cid, idx, t) => p2pTryFetchSegment(cid, String(idx), t);
const rememberCell = (cid, idx)    => rememberSegment(cid, String(idx));

const GATEWAY_URL = 'http://127.0.0.1:8801';
const MORM_RPC    = 'http://127.0.0.1:8900';

const PREFETCH_RATIO = 0.10;
const PURGE_RATIO    = 0.50;
const CELL_DURATION  = 3.0;

const EDGES = [
  { url: 'http://127.0.0.1:8787' },           // origin
  { url: 'http://127.0.0.1:8788' },           // mirror-A (optional)
  { url: 'http://127.0.0.1:8789' },           // mirror-B (optional)
];

const $ = id => document.getElementById(id);
const select = $('content-select');
const cellBar = $('cell-bar');
const pulseEl = $('pulse');
const peersListEl = $('peers-list');

const stat = { loaded: 0, purged: 0, bytes: 0, pulse: 0, fetched: new Set() };
const peerHits = new Map();    // url -> count of successful cell fetches
const peerInfo = new Map();    // url -> { node_id, role, online }
let state = null;

function shuffle(arr) {
  const a = arr.slice();
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

async function probePeer(edge) {
  try {
    const r = await fetch(`${edge.url}/api/node/info`, { cache: 'no-store' });
    if (!r.ok) throw new Error('not ok');
    const j = await r.json();
    peerInfo.set(edge.url, { node_id: j.node_id, role: j.role, online: true });
  } catch {
    peerInfo.set(edge.url, { node_id: edge.url.replace('http://', ''), role: '?', online: false });
  }
}

function renderPeers() {
  peersListEl.innerHTML = '';
  for (const edge of EDGES) {
    const info = peerInfo.get(edge.url) || { node_id: edge.url, role: '?', online: false };
    const hits = peerHits.get(edge.url) || 0;
    const li = document.createElement('li');
    li.innerHTML = `
      <span class="peer-dot ${info.online ? 'online' : 'offline'}"></span>
      <span class="peer-name">${info.node_id}<span class="peer-role">${info.role}</span></span>
      <span class="peer-count">${hits}</span>
    `;
    peersListEl.appendChild(li);
  }
}

async function refreshPeers() {
  await Promise.all(EDGES.map(probePeer));
  renderPeers();
}

async function fetchFromAnyEdge(path) {
  // try edges in random order so load distributes across the swarm
  const order = shuffle(EDGES);
  let lastErr;
  for (const edge of order) {
    if (peerInfo.get(edge.url) && !peerInfo.get(edge.url).online) continue;
    try {
      const r = await fetch(`${edge.url}${path}`, { cache: 'no-store' });
      if (!r.ok) { lastErr = new Error(`${edge.url} returned ${r.status}`); continue; }
      peerHits.set(edge.url, (peerHits.get(edge.url) || 0) + 1);
      renderPeers();
      return r;
    } catch (e) {
      // peer unreachable — mark offline and try next
      const info = peerInfo.get(edge.url) || {};
      peerInfo.set(edge.url, { ...info, online: false });
      renderPeers();
      lastErr = e;
    }
  }
  throw lastErr || new Error('no peer responded');
}

async function fetchContents() {
  const r = await fetchFromAnyEdge('/api/contents');
  return (await r.json()).contents;
}
async function fetchManifest(cid) {
  const r = await fetchFromAnyEdge(`/api/manifest/${cid}`);
  return r.json();
}
async function fetchCellBlob(cid, index) {
  // Phase 22: try a peer over WebRTC first; fall back to the edge swarm.
  let blob = null;
  try {
    blob = await p2pTryFetch(cid, index, 2500);
  } catch {}
  if (!blob) {
    const r = await fetchFromAnyEdge(`/api/cell/${cid}/${index}`);
    blob = await r.blob();
  } else {
    flashPulse(`p2p · cell ${index}`);
  }
  rememberCell(cid, index);
  stat.bytes += blob.size;
  $('stat-bytes').textContent = `${(stat.bytes / 1024).toFixed(1)} KB`;
  refreshP2PHud();
  return blob;
}

let observedPeerCount = 0;
function refreshP2PHud() {
  const s = p2pStats();
  const peers = Math.max(s.peerCount, observedPeerCount);
  const el = $('stat-p2p');
  if (el) el.textContent = `${s.p2pHits} hits · ${peers} peers · ${s.iceMode || '?'}`;
}
// poll the signaling server every 4s so peer count updates even when no
// cell fetch is in flight (lets the user see other tabs join immediately)
setInterval(async () => {
  try {
    const cid = document.getElementById('content-select')?.value;
    if (!cid) return;
    const me = sessionStorage.getItem('morm-peer-id') || '';
    const r = await fetch(`/api/signal/peers/${cid}?exclude=${me}`);
    const j = await r.json();
    observedPeerCount = j.peers.length;
    refreshP2PHud();
  } catch {}
}, 2500);

function renderCellBar(n) {
  cellBar.innerHTML = '';
  for (let i = 0; i < n; i++) {
    const t = document.createElement('span');
    t.className = 'cell-tick';
    t.dataset.index = i;
    cellBar.appendChild(t);
  }
}
function setCellState(index, cls) {
  const el = cellBar.querySelector(`[data-index="${index}"]`);
  if (!el) return;
  if (cls === 'active') {
    cellBar.querySelectorAll('.cell-tick.active').forEach(e =>
      e.classList.remove('active'));
  }
  el.classList.add(cls);
}
function flashPulse(text) {
  pulseEl.textContent = text;
  pulseEl.classList.add('flash');
  setTimeout(() => pulseEl.classList.remove('flash'), 220);
}

function ensureVideo() {
  const wrap = document.querySelector('.player-wrap');
  for (const id of ['player', 'player-b']) {
    const e = document.getElementById(id);
    if (e) e.remove();
  }
  const oldStack = wrap.querySelector('.video-stack');
  if (oldStack) oldStack.remove();
  const v = document.createElement('video');
  v.id = 'player'; v.muted = true; v.playsInline = true; v.controls = false; v.preload = 'auto';
  Object.assign(v.style, {
    width: '100%', maxWidth: '480px', aspectRatio: '9/16',
    background: '#000', borderRadius: '8px',
  });
  wrap.insertBefore(v, wrap.firstChild);
  return v;
}

async function play(content) {
  if (state?.cleanup) state.cleanup();
  stat.loaded = stat.purged = stat.bytes = stat.pulse = 0;
  stat.fetched = new Set();
  $('stat-loaded').textContent = '0';
  $('stat-purged').textContent = '0';
  $('stat-bytes').textContent = '0 KB';
  $('stat-pulse').textContent = '0.000';
  $('stat-buffered').textContent = '—';
  $('stat-active').textContent = '—';

  const manifest = await fetchManifest(content.content_id);
  const numCells = manifest.cells.length;
  renderCellBar(numCells);
  setP2PContent(content.content_id);   // begin announcing as a peer
  refreshP2PHud();

  const player = ensureVideo();
  const blobUrls = new Map();
  let activeIndex = -1;
  const prefetchTriggered = new Set();

  state = {
    cleanup: () => { blobUrls.forEach(u => URL.revokeObjectURL(u)); blobUrls.clear(); },
  };

  async function loadCell(i) {
    if (i >= numCells || blobUrls.has(i) || stat.fetched.has(i)) return;
    stat.fetched.add(i);
    const blob = await fetchCellBlob(content.content_id, i);
    const url = URL.createObjectURL(blob);
    blobUrls.set(i, url);
    stat.loaded++; stat.pulse += 0.01;
    $('stat-loaded').textContent = stat.loaded;
    $('stat-pulse').textContent = stat.pulse.toFixed(3);
    setCellState(i, 'loaded');
    flashPulse(`+0.01 MORM · cell ${i}`);
  }
  function purgeCell(i) {
    const url = blobUrls.get(i);
    if (!url) return;
    URL.revokeObjectURL(url);
    blobUrls.delete(i);
    setCellState(i, 'purged');
    stat.purged++;
    $('stat-purged').textContent = stat.purged;
    $('stat-buffered').textContent = `holding ${blobUrls.size} cells`;
  }
  async function setPlaying(idx) {
    activeIndex = idx;
    setCellState(idx, 'active');
    $('stat-active').textContent = `cell ${idx}`;
    $('stat-buffered').textContent = `holding ${blobUrls.size} cells`;
    if (!blobUrls.has(idx)) await loadCell(idx);
    player.src = blobUrls.get(idx);
    try { await player.play(); } catch {}
    // fire-and-forget: claim view_reward on chain (idempotent per cell)
    tryClaim(content.content_id, idx);
  }

  player.addEventListener('timeupdate', () => {
    const t = player.currentTime;
    const dur = player.duration || CELL_DURATION;
    const ratio = dur > 0 ? t / dur : 0;
    if (ratio >= PREFETCH_RATIO && !prefetchTriggered.has(activeIndex + 1)
        && activeIndex + 1 < numCells) {
      prefetchTriggered.add(activeIndex + 1);
      loadCell(activeIndex + 1).catch(() => {});
    }
    if (ratio >= PURGE_RATIO) {
      for (let i = 0; i <= activeIndex - 1; i++) {
        if (blobUrls.has(i)) purgeCell(i);
      }
    }
  });

  player.addEventListener('ended', () => {
    const next = activeIndex + 1;
    if (next < numCells) setPlaying(next);
  });

  await loadCell(0);
  await setPlaying(0);
  loadCell(1).catch(() => {});
}

// ---- MORM identity + on-chain view_reward claim --------------------------

let identity = null;
let claimsAttempted = new Set();   // `${cid}:${idx}` per content/cell — debounce
let claimedCells = 0;

async function refreshIdentity() {
  try {
    const ids = await listIdentities();
    identity = ids[0] || null;
  } catch { identity = null; }
  $('ident-addr').textContent = identity ? identity.address : '— (sign in via passkey gateway)';
  if (identity) refreshIdentityBalance();
}

async function refreshIdentityBalance() {
  if (!identity) return;
  try {
    const r = await fetch(`${MORM_RPC}/account/${identity.address}`);
    const a = await r.json();
    $('ident-bal').textContent = `${a.balance} MORM`;
  } catch {
    $('ident-bal').textContent = '— (RPC unreachable)';
  }
}

async function tryClaim(contentId, cellIdx) {
  if (!identity) return;
  const key = `${contentId}:${cellIdx}`;
  if (claimsAttempted.has(key)) return;
  claimsAttempted.add(key);
  try {
    const res = await claimViewReward({
      gatewayUrl: GATEWAY_URL, mormRpc: MORM_RPC, identity,
      contentId, cellIndex: cellIdx,
    });
    if (res.ok) {
      claimedCells++;
      $('ident-claims').textContent = claimedCells;
      flashPulse(`+1 MORM · cell ${cellIdx} claimed`);
      setTimeout(refreshIdentityBalance, 1500);
    }
  } catch (e) {
    console.warn('claim failed', e);
  }
}

async function init() {
  await refreshPeers();
  // poll peers periodically so on-the-fly node restarts show up
  setInterval(refreshPeers, 5000);
  await refreshIdentity();
  setInterval(refreshIdentity, 10_000);

  const contents = await fetchContents();
  if (!contents.length) {
    select.innerHTML = '<option>(no accepted contents — run morm-core screen first)</option>';
    return;
  }
  select.innerHTML = contents.map(c =>
    `<option value="${c.content_id}">${c.creator_id} · ${c.content_id.slice(0,12)}…${c.generation_id ? ' · AI' : ''}</option>`
  ).join('');
  select.addEventListener('change', () => {
    const c = contents.find(x => x.content_id === select.value);
    if (c) play(c);
  });
  play(contents[0]);
}

init().catch(e => {
  console.error(e);
  document.body.insertAdjacentHTML('beforeend',
    `<pre style="color:#f88;padding:24px">init failed: ${e.message}</pre>`);
});
