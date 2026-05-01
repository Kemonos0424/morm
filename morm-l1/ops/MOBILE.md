# MORM Mobile — Smartphones as Light Nodes

## What a phone can do (Phase 21)

Smartphones can't realistically run a producer (battery + OS background
restrictions kill long-running processes), but they're a perfect fit for
the **Light Node** role from MORM.md §2:

> Light Node (User Device): スマホやゲーム機 — 自分の視聴に必要なデータだけ
> を検証し、余剰リソースで他者のための「3秒」を中継する。

What ships in Phase 21:

- **PWA manifest** + apple-touch icons → "Add to Home Screen" makes the
  swarm/shop/wallet open like a native app, in standalone fullscreen.
- **Service Worker** at root scope:
  - shell (HTML/CSS/JS/icons): cache-first
  - `/api/cell/{cid}/{n}`: stale-while-revalidate, infinite TTL
    (cells are content-addressed, any cache hit is correct)
  - everything else: network-first
- **Mobile camera** — `getUserMedia({facingMode:'environment'})` so the
  Shop's evidence flow uses the back camera by default; falls back to
  the front camera if no rear cam.
- **Touch tweaks** in `style.css` — `touch-action: manipulation`,
  `-webkit-tap-highlight-color: transparent`, `safe-area-inset-*`
  padding, no overscroll bounce on the player.

## Adding the app to a phone (real device)

Pre-req: the gateway is reachable from the phone — same Wi-Fi or via a
tunnel (see `TESTNET.md`).

**iOS / Safari**

1. Open `https://<gateway-host>/player`
2. Share → "Add to Home Screen"
3. Open from the new home-screen icon — runs standalone, status-bar
   integrated, theme-color blue.

**Android / Chrome**

1. Open `https://<gateway-host>/player`
2. ⋮ menu → "Install app" (or the in-page install banner)
3. Launches as a standalone WebAPK with the MORM icon.

> Service Worker registration only happens on `https://` or
> `http://localhost`. Behind a Cloudflare/Tailscale tunnel that's already
> the case; if you're testing over plain LAN, you'll need a local TLS
> proxy (e.g. `caddy reverse-proxy --to :8801`) to enable SW + PWA install.

## Light-Node behaviour (cell cache)

Once the SW is active, every cell the user watches is silently written
to a `morm-cells-v1` Cache, keyed by full URL. The next visit
re-uses it without hitting the edge. Offline playback works as long as
the cells were previously fetched.

To inspect on a phone:
- iOS: Safari → Settings → Advanced → Web Inspector (with Mac)
- Android: chrome://inspect from desktop Chrome (USB-debug)

DevTools → Application → Cache Storage → `morm-cells-v1`.

## Identity & passkeys

MORM IDs work the same as on desktop (Phase 7 + 9 + 11b):

- iOS Face ID / Touch ID and Android biometric prompts back the WebAuthn
  ceremony directly. The XOR client-share is stored in IndexedDB, which
  the PWA persists across launches.
- The browser-side `signTx` (ed25519 via `@noble/ed25519`) runs natively
  on the phone — **no key ever leaves the device** beyond the
  server-share fragment, which alone is useless.

## Things mobile **can't** do (yet)

- **Run a producer** — block production needs an always-on process.
  Pair the phone with a Mac mini / Raspberry Pi via `ops/invite-node.sh`
  and use the phone as a Light client of *that* node.
- **Mirror long-tail content** — mobile cache is bounded; the SW will
  evict on quota pressure. For real Edge mirroring, install
  `morm-player/server.py` on a stationary device.
- **WebRTC peer mirror** — Phase 21 caches locally and relays via the
  edge; phone-to-phone direct relay (true Light-Node mesh) is a Phase 22
  candidate.

## Quick smoke test

```bash
# from your laptop, expose the gateway:
cloudflared tunnel --url http://127.0.0.1:8801
# → grab the assigned https://… URL, open it on the phone

# verify on the phone:
#  1. /player loads, video plays (cells cached on second visit)
#  2. /shop with camera button uses the back camera
#  3. "Add to Home Screen" creates a standalone icon
#  4. enabling airplane mode + reopening still plays the recently-watched cells
```
