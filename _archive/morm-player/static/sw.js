// MORM Service Worker — mobile Light Node behaviour
//
// Spec ref: MORM.md §2 — "Light Node: 自分の視聴に必要なデータだけを検証し、
// 余剰リソースで他者のための『3秒』を中継する". Phase 21 makes the browser
// itself a tiny mirror: every fetched cell is cached locally, and offline
// reads fall back to the cache instead of going to the edge.
//
// Strategy:
//   - shell (HTML/CSS/JS/icons): cache-first, network-fallback (24h max-age)
//   - /api/cell/{cid}/{n}:        stale-while-revalidate against the cache
//   - everything else:            network-first
//
// Phase 26y — guard against stale code:
//   - Every cached SHELL response is checked against a 24h max-age via the
//     `date` header set by the gateway. Older hits are bypassed in favour
//     of a network fetch (which re-stores a fresh copy on success).
//   - On `activate` we hit GET /sw-version and compare the returned hash
//     to the value the SW saw on its prior activate. A mismatch triggers
//     a full purge of every SW-owned cache before any request is served.
//     This shortens the window where a script-kiddie's old cached shell
//     can keep running after the upstream fix lands. The version itself
//     is stored under `morm-meta-v1` (a single special-purpose cache) so
//     we can persist it without touching IndexedDB.

const VERSION = 'morm-sw-v2';                    // Phase 26y bump
const SHELL   = `morm-shell-${VERSION}`;
const CELLS   = `morm-cells-${VERSION}`;
const META    = `morm-meta-v1`;                  // versioning side-cache
const META_VERSION_KEY = '/__morm_sw_version__'; // synthetic URL key

const SHELL_FILES = [
  '/manifest.webmanifest',
  '/static/style.css',
  '/static/morm-identity.js',
  '/static/icons/morm-192.svg',
  '/static/icons/morm-512.svg',
];

// Shell entries older than this are treated as cache misses. 24h matches
// SECURITY-DESIGN §1.7 26y's max-age guidance — long enough that offline
// users still load the app on a flight, short enough that buggy code
// can't survive a deploy + airtime + a single full day.
const SHELL_MAX_AGE_MS = 24 * 60 * 60 * 1000;

self.addEventListener('install', e => {
  self.skipWaiting();
  e.waitUntil(caches.open(SHELL).then(c => c.addAll(SHELL_FILES)));
});

// Phase 26y — shared logic between `activate` and the explicit recheck
// message handler. Returns true if the upstream version differed and a
// purge was performed.
async function _recheckVersionAndMaybePurge() {
  let mismatch = false;
  try {
    const r = await fetch('/sw-version', { cache: 'no-store' });
    if (r.ok) {
      const { version } = await r.json();
      const meta = await caches.open(META);
      const prev = await meta.match(META_VERSION_KEY);
      const prevVersion = prev ? await prev.text() : null;
      if (version && prevVersion !== version) {
        mismatch = true;
        await meta.put(
          META_VERSION_KEY,
          new Response(version, { headers: { 'Content-Type': 'text/plain' }}));
      }
    }
  } catch { /* offline / rate-limited — keep current caches */ }

  const keep = new Set([SHELL, CELLS, META]);
  for (const k of await caches.keys()) {
    if (!keep.has(k) || (mismatch && k !== META)) {
      await caches.delete(k);
    }
  }
  return mismatch;
}

self.addEventListener('activate', e => {
  e.waitUntil((async () => {
    await _recheckVersionAndMaybePurge();
    await self.clients.claim();
  })());
});

// Phase 26y — page-driven recheck. Browsers only fire `activate` when the
// SW *script* changes; if only the SHELL files change, activate never
// runs and the cache could keep serving the old build. The page sends
// {type: 'morm-sw-recheck'} on load (and on visibilitychange) to force
// a check now. The reply via MessageChannel reports {mismatch: bool}.
self.addEventListener('message', e => {
  const data = e.data;
  if (data && data.type === 'morm-sw-recheck') {
    e.waitUntil((async () => {
      const mismatch = await _recheckVersionAndMaybePurge();
      if (e.ports && e.ports[0]) {
        e.ports[0].postMessage({ mismatch });
      }
    })());
  }
});

self.addEventListener('fetch', event => {
  const req = event.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);

  // /api/cell/{cid}/{n} — stale-while-revalidate, infinite TTL (cells are
  // content-addressed so any hit is correct).
  if (/^\/api\/cell\/[0-9a-f]+\/\d+$/.test(url.pathname)) {
    event.respondWith(staleWhileRevalidate(CELLS, req));
    return;
  }
  // Manifest & static shell. We special-case JS as network-first so that
  // developing in-place doesn't get pinned to a stale module by the cache;
  // the rest (CSS, manifest, icons) is cache-first for offline.
  if (url.pathname.endsWith('.js')) {
    event.respondWith(networkFirst(req));
    return;
  }
  if (url.pathname.startsWith('/static/') || url.pathname === '/manifest.webmanifest') {
    event.respondWith(cacheFirst(SHELL, req));
    return;
  }
  // RPC, /api, everything else — network-first
  event.respondWith(networkFirst(req));
});

async function staleWhileRevalidate(cacheName, req) {
  const cache = await caches.open(cacheName);
  const cached = await cache.match(req);
  const fetchPromise = fetch(req).then(res => {
    if (res.ok && res.status === 200) cache.put(req, res.clone());
    return res;
  }).catch(() => null);
  return cached || (await fetchPromise) || new Response('cache miss', { status: 504 });
}

// Phase 26y — `cacheFirst` enforces the 24h ceiling. The Date header is
// set by the gateway (BaseHTTPRequestHandler always emits it), so we can
// trust it for staleness checks. If the cached entry is too old we fall
// through to the network and refresh the cache on a successful 200.
function _cachedTooOld(res) {
  if (!res) return false;
  const d = res.headers.get('date');
  if (!d) return false;
  const t = Date.parse(d);
  if (!Number.isFinite(t)) return false;
  return (Date.now() - t) > SHELL_MAX_AGE_MS;
}

async function cacheFirst(cacheName, req) {
  const cache = await caches.open(cacheName);
  const hit = await cache.match(req);
  if (hit && !_cachedTooOld(hit)) return hit;
  const res = await fetch(req).catch(() => null);
  if (res && res.ok) cache.put(req, res.clone());
  // If the network failed BUT we have a stale cache hit, prefer the
  // stale data over a 503 — this keeps the offline path working.
  return res || hit || new Response('offline', { status: 503 });
}
async function networkFirst(req) {
  try {
    return await fetch(req);
  } catch {
    const c = await caches.match(req);
    return c || new Response('offline', { status: 503 });
  }
}
