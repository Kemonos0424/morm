// Phase 25Va — HLS player with VIEW_REWARD claim per segment.
// Phase 22-Video — opportunistic P2P fetch of .m4s segments via WebRTC.
// Phase 25-Video portrait pivot + swipe-feed (2026-04-30) —
//   Renders a TikTok/Reels-style scroll-snap feed of 9:16 cards. The
//   browser's native scroll-snap handles the swipe; an
//   IntersectionObserver decides which video is "active" and binds
//   hls.js + P2P announce + VIEW_REWARD claims to it. Inactive videos
//   are paused with no hls.js attached, so memory + bandwidth stay flat
//   regardless of how many contents the gateway lists.

import { listIdentities, claimViewReward } from '/static/morm-identity.js';
import {
  p2pStats, setP2PContent,
  p2pTryFetchSegment, rememberSegment,
} from '/static/morm-p2p.js';
import { t, mountLangToggle } from '/static/morm-i18n.js';
import { maybeShowFirstTimeGuide, mountHelpButton, STEPS } from '/static/morm-guide.js';

const GATEWAY_URL = window.location.origin;
let MORM_RPC = 'http://127.0.0.1:8900';
async function _resolveRpc() {
  try {
    const r = await fetch(`${GATEWAY_URL}/api/morm/info`);
    if (r.ok) {
      const j = await r.json();
      if (j.rpc) MORM_RPC = j.rpc;
    }
  } catch {}
}

const $ = id => document.getElementById(id);
const feedEl  = $('feed');
const pagerEl = $('pager');
const emptyEl = $('empty');

let identity = null;
let activeContentId = null;       // currently-foreground content
let activeHls = null;             // hls.js attached to the active <video>
let activeVideo = null;
const claimsAttempted = new Set(); // `${cid}:${idx}`
const itemState = new Map();       // cid -> {videoEl, hudEl, claimedCells, segs, level}

// ------------------------------------------------------------------
// Custom hls.js fragment loader: P2P first, origin fallback. Re-used
// across active video swaps.
// ------------------------------------------------------------------
function parseSegUrl(url) {
  try {
    const u = new URL(url, GATEWAY_URL);
    const m = u.pathname.match(
      /^\/api\/video\/([0-9a-f]+)\/([0-9a-zA-Z_]+)\/([\w.\-]+)$/);
    if (!m) return null;
    const file = m[3];
    if (!(file.endsWith('.m4s') || file.endsWith('.mp4'))) return null;
    return { cid: m[1], segId: `${m[2]}/${file}` };
  } catch { return null; }
}

async function seedP2PCache(url, data, segId) {
  try {
    const cache = await caches.open('morm-hls-v1');
    const buf = data instanceof ArrayBuffer ? data : data.buffer;
    await cache.put(url, new Response(buf, { headers: {
      'Content-Type': segId.endsWith('.mp4') ? 'video/mp4' : 'video/iso.segment',
      'Cache-Control': 'public, max-age=31536000, immutable',
    }}));
  } catch (e) { /* quota / opaque */ }
}

function buildP2PLoader(Hls) {
  const Base = Hls.DefaultConfig.loader;
  return class P2PFragLoader extends Base {
    load(context, config, callbacks) {
      const seg = parseSegUrl(context.url);
      if (!seg || !activeContentId || seg.cid !== activeContentId) {
        return super.load(context, config, callbacks);
      }
      const t0 = performance.now();
      const wrapped = {
        ...callbacks,
        onSuccess: (resp, stats, ctx, net) => {
          if (resp?.data) {
            seedP2PCache(context.url, resp.data, seg.segId);
            rememberSegment(seg.cid, seg.segId);
          }
          callbacks.onSuccess(resp, stats, ctx, net);
        },
      };
      const onMiss = () => super.load(context, config, wrapped);
      p2pTryFetchSegment(seg.cid, seg.segId, 1500).then(blob => {
        if (!blob) return onMiss();
        return blob.arrayBuffer().then(buf => {
          const tload = performance.now();
          const stats = this.stats || {};
          stats.aborted = false;
          stats.loaded = buf.byteLength;
          stats.total  = buf.byteLength;
          stats.loading   = { start: t0, first: tload, end: tload };
          stats.parsing   = { start: tload, end: tload };
          stats.buffering = { start: tload, first: tload, end: tload };
          stats.retry = 0;
          stats.chunkCount = 0;
          stats.bwEstimate = (buf.byteLength * 8)
            / Math.max(0.001, (tload - t0) / 1000);
          callbacks.onSuccess(
            { url: context.url, data: buf },
            stats, context, null,
          );
        });
      }).catch(e => {
        console.warn('p2p fragment loader fallback', e);
        onMiss();
      });
    }
  };
}

// ------------------------------------------------------------------
// VIEW_REWARD claims (per active item).
// ------------------------------------------------------------------
async function tryClaim(contentId, segIdx) {
  if (!identity) return;
  const key = `${contentId}:${segIdx}`;
  if (claimsAttempted.has(key)) return;
  claimsAttempted.add(key);
  try {
    const res = await claimViewReward({
      gatewayUrl: GATEWAY_URL, mormRpc: MORM_RPC, identity,
      contentId, cellIndex: segIdx,
    });
    if (res?.morm_response?.ok || res?.ok) {
      const st = itemState.get(contentId);
      if (st) {
        st.claimedCells = (st.claimedCells || 0) + 1;
        renderItemHud(contentId);
      }
      setTimeout(refreshBalance, 1200);
    }
  } catch {}
}

async function refreshBalance() {
  if (!identity) return;
  try {
    const r = await fetch(`${MORM_RPC}/account/${identity.address}`);
    const a = await r.json();
    $('ident-bal').textContent = `${a.balance} MORM`;
  } catch {
    $('ident-bal').textContent = '—';
  }
}

async function refreshIdentity() {
  try {
    const ids = await listIdentities();
    identity = ids[0] || null;
  } catch { identity = null; }
  $('ident-addr').textContent = identity ? identity.address : t('common.identity_unset');
  if (identity) refreshBalance();
}

// ------------------------------------------------------------------
// Per-item HUD overlay — written on every claim/segment change so the
// active video shows fresh stats without a global refresh tick.
// ------------------------------------------------------------------
function renderItemHud(cid) {
  const st = itemState.get(cid);
  if (!st) return;
  const s = p2pStats();
  const hud = st.hudEl;
  hud.querySelector('.cid').textContent = cid;
  const row = hud.querySelector('.row');
  row.innerHTML =
    `<span>level <b>${st.level || '—'}</b></span>` +
    `<span>seg <b>${st.segs}</b></span>` +
    `<span>claims <b>${st.claimedCells}</b></span>` +
    `<span>p2p <b>${cid === activeContentId ? s.p2pHits : 0}</b></span>` +
    `<span>peers <b>${cid === activeContentId ? s.peerCount : 0}</b></span>` +
    `<span>ice <b>${s.iceMode || '—'}</b></span>`;
}
// Periodic light refresh just for the active item's P2P numbers.
setInterval(() => { if (activeContentId) renderItemHud(activeContentId); }, 1000);

// ------------------------------------------------------------------
// Active-video binding. When an item scrolls past the activation
// threshold, we mount hls.js on its <video>, set up FRAG_LOADED claim
// hooks, and switch the P2P announcer to that content_id. The previously
// active video is paused and its hls.js destroyed so we never have more
// than one media pipeline live at a time.
// ------------------------------------------------------------------
const forceHlsJs = /[?&]force-hlsjs(?:=|$)/.test(location.search);

function destroyActive() {
  if (activeHls) { try { activeHls.destroy(); } catch {} }
  activeHls = null;
  if (activeVideo) {
    try {
      activeVideo.pause();
      activeVideo.removeAttribute('src');
      activeVideo.load();
    } catch {}
  }
  activeVideo = null;
  activeContentId = null;
}

function activate(cid, videoEl) {
  if (cid === activeContentId) return;
  destroyActive();
  activeContentId = cid;
  activeVideo = videoEl;
  // Tell P2P the foreground content; announces start, listPeers will
  // discover other tabs viewing the same cid.
  setP2PContent(cid);
  const src = `${GATEWAY_URL}/api/video/${cid}/master.m3u8`;
  // Native HLS path (iOS Safari) — no custom loader, but VIEW_REWARD
  // claims still happen via timeupdate.
  if (!forceHlsJs && videoEl.canPlayType('application/vnd.apple.mpegurl')) {
    videoEl.src = src;
    let lastSeg = -1;
    const tu = () => {
      const seg = Math.floor(videoEl.currentTime / 3);
      if (seg !== lastSeg) {
        lastSeg = seg;
        const st = itemState.get(cid);
        if (st) { st.segs += 1; renderItemHud(cid); }
        tryClaim(cid, seg);
      }
    };
    videoEl.addEventListener('timeupdate', tu);
    videoEl.play().catch(() => {});
    return;
  }
  if (window.Hls && window.Hls.isSupported()) {
    const Hls = window.Hls;
    activeHls = new Hls({
      lowLatencyMode: false,
      enableWorker: true,
      fLoader: buildP2PLoader(Hls),
    });
    activeHls.loadSource(src);
    activeHls.attachMedia(videoEl);
    activeHls.on(Hls.Events.MANIFEST_PARSED, () => {
      videoEl.play().catch(() => {});
    });
    activeHls.on(Hls.Events.LEVEL_SWITCHED, (_e, data) => {
      const lvl = activeHls.levels?.[data.level];
      if (lvl) {
        const shortDim = Math.min(lvl.width || lvl.height, lvl.height || lvl.width);
        const st = itemState.get(cid);
        if (st) { st.level = `${shortDim}p`; renderItemHud(cid); }
      }
    });
    activeHls.on(Hls.Events.FRAG_LOADED, (_e, data) => {
      const sn = data?.frag?.sn;
      const url = data?.frag?.url || '';
      const seg = parseSegUrl(url);
      if (seg && seg.cid === cid) rememberSegment(cid, seg.segId);
      if (typeof sn === 'number') {
        const st = itemState.get(cid);
        if (st) { st.segs += 1; renderItemHud(cid); }
        tryClaim(cid, sn);
      }
    });
  }
}

// ------------------------------------------------------------------
// Feed construction.
// ------------------------------------------------------------------
async function fetchContents() {
  const r = await fetch(`${GATEWAY_URL}/api/video/list`);
  if (!r.ok) throw new Error(`list ${r.status}`);
  return (await r.json()).contents || [];
}

function makeFeedItem(c, idx, total) {
  const item = document.createElement('article');
  item.className = 'feed-item';
  item.dataset.cid = c.content_id;
  item.dataset.idx = String(idx);

  const v = document.createElement('video');
  v.setAttribute('playsinline', '');
  v.setAttribute('controls', '');
  v.muted = true;     // autoplay needs muted; user can unmute
  v.preload = 'metadata';
  item.appendChild(v);

  // Tap to play/pause when interacting with the active card
  const tap = document.createElement('div');
  tap.className = 'tap';
  tap.addEventListener('click', () => {
    if (v.paused) v.play().catch(()=>{});
    else v.pause();
  });
  item.appendChild(tap);

  const hud = document.createElement('div');
  hud.className = 'item-hud';
  hud.innerHTML =
    `<div class="pos">${idx + 1} / ${total}</div>` +
    `<div class="cid">${c.content_id}</div>` +
    `<div class="row"></div>`;
  item.appendChild(hud);

  itemState.set(c.content_id, {
    videoEl: v, hudEl: hud, claimedCells: 0, segs: 0, level: null,
  });
  renderItemHud(c.content_id);
  return item;
}

function renderPager(n) {
  pagerEl.innerHTML = '';
  for (let i = 0; i < n; i++) {
    const d = document.createElement('div');
    d.className = 'dot';
    d.dataset.idx = String(i);
    pagerEl.appendChild(d);
  }
}
function setPagerActive(idx) {
  pagerEl.querySelectorAll('.dot').forEach(d => {
    d.classList.toggle('active', Number(d.dataset.idx) === idx);
  });
}

async function buildFeed() {
  let contents = [];
  try { contents = await fetchContents(); } catch (e) {
    emptyEl.textContent = t('player.empty.error', { err: e.message });
    return;
  }
  if (!contents.length) {
    emptyEl.textContent = t('player.empty.none');
    return;
  }
  emptyEl.remove();
  feedEl.innerHTML = '';
  contents.forEach((c, i) => feedEl.appendChild(makeFeedItem(c, i, contents.length)));
  renderPager(contents.length);

  // IntersectionObserver — activate whichever item is most in-view.
  // Threshold 0.6 means roughly "more than half the card visible";
  // scroll-snap aligns each card to a stop, so this triggers cleanly
  // on every snap.
  const obs = new IntersectionObserver(entries => {
    let best = null;
    for (const e of entries) {
      if (e.isIntersecting && e.intersectionRatio > 0.6) {
        if (!best || e.intersectionRatio > best.intersectionRatio) best = e;
      }
    }
    if (!best) return;
    const cid = best.target.dataset.cid;
    const idx = Number(best.target.dataset.idx);
    setPagerActive(idx);
    const v = best.target.querySelector('video');
    activate(cid, v);
  }, { root: feedEl, threshold: [0, 0.6, 1.0] });
  feedEl.querySelectorAll('.feed-item').forEach(it => obs.observe(it));
}

(async function init() {
  // Mount language toggle + help (?) button into the topbar before any
  // string render so the first-time guide overlay finds its anchors.
  mountLangToggle($('lang-toggle') || document.body);
  mountHelpButton($('help-btn') || document.body, 'player', STEPS.player);
  // Re-paint dynamic strings on language change (data-i18n auto-applies).
  window.addEventListener('morm-lang-changed', () => refreshIdentity());
  await _resolveRpc();
  await refreshIdentity();
  setInterval(refreshIdentity, 10_000);
  await buildFeed();
  // First-time onboarding — explains swipe + per-segment rewards + P2P.
  maybeShowFirstTimeGuide('player', STEPS.player);
})();
