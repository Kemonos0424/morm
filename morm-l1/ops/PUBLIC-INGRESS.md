# Public Ingress for a MORM Node — Phase 30f

> Last sync: 2026-05-07

A self-installed MORM node behind a NAT, CGNAT, or residential ISP can't
accept inbound connections from peers or browsers. To participate in the
federation as a discoverable seed (or just to share your `/swap`,
`/upload`, `/player-hls` with friends), you need a tunnel.

This doc covers the two opt-in tunnel sidecars shipped in
`docker/morm-node.docker-compose.yml` (Compose profiles `tunnel-cf` and
`tunnel-ts`).

## What gets exposed (and what doesn't)

Both sidecars publish only the **gateway service** (browser-facing port
8801) to the public internet. The L1 RPC (8900) and the Edge service
(8787) stay inside the compose network.

This is deliberate:

- The browser routes (`/auth-morm`, `/upload`, `/player-hls`, `/wallet`,
  `/swap`, `/admin`) **need** public reach for a usable network.
- The L1 RPC accepts unsigned `/credit` and other dev endpoints in
  `--dev-mode`. Exposing it publicly without first turning dev-mode off
  (`MORM_PRODUCTION=1`) is a footgun. The compose default keeps it
  internal.
- The Edge service hosts HLS bytes that the gateway already proxies
  via `/api/video/...`, so a separate public path adds no value.

If you eventually want the L1 RPC public (so other nodes can sync from
yours), add a second tunnel route pointing at `l1:8900` — but only after
disabling dev-mode and reviewing `morm-l1/ops/SECURITY-DESIGN.md`.

## Choice A — Cloudflare Tunnel (recommended for first-time)

Cloudflare provides a free anycast tunnel terminating at their edge.
You don't need a public IP, port forwarding, or even a Cloudflare paid
plan — but you do need a domain on Cloudflare DNS (you can get a free
one or pay $10/year at any registrar and point its NS to Cloudflare).

```bash
# 1. install cloudflared on the host (one-time)
brew install cloudflared        # macOS
# Linux: see https://pkg.cloudflare.com/cloudflared/

# 2. authenticate once (opens browser)
cloudflared tunnel login

# 3. create a named tunnel and route a hostname to it
cloudflared tunnel create morm-1
cloudflared tunnel route dns morm-1 morm.example.com

# 4. dump the tunnel credentials and copy the token printed on stdout
cloudflared tunnel token morm-1   # copy output verbatim

# 5. set CLOUDFLARED_TOKEN in docker/.env, then:
cd ~/morm
docker compose -f docker/morm-node.docker-compose.yml \
    --env-file docker/.env \
    --profile tunnel-cf up -d

# 6. wait ~30s, then visit https://morm.example.com/auth-morm
```

The tunnel container points its single ingress at `gateway:8801` (the
compose-internal name) and Cloudflare terminates TLS at the edge.

**To stop:** `docker compose --profile tunnel-cf down`

## Choice B — Tailscale Funnel

If you're already on Tailscale, Funnel exposes a single Tailscale node
on a public-internet TLS endpoint at `<hostname>.<your-tailnet>.ts.net`.
This is simpler than Cloudflare if you're a Tailscale user, but it
requires a Tailscale account.

```bash
# 1. on the Tailscale admin page, create a one-shot reusable auth key:
#    https://login.tailscale.com/admin/settings/keys

# 2. set TS_AUTHKEY in docker/.env (and optionally TS_HOSTNAME)

# 3. EDIT docker/tunnel-ts/funnel.json — replace
#    'morm-node.YOUR-TAILNET.ts.net' with your assigned hostname.
#    You can preview your hostname after first auth via:
#       docker compose run --rm tunnel-ts tailscale status

# 4. start
cd ~/morm
docker compose -f docker/morm-node.docker-compose.yml \
    --env-file docker/.env \
    --profile tunnel-ts up -d

# 5. visit https://morm-node.YOUR-TAILNET.ts.net/auth-morm
```

**Note**: Tailscale Funnel currently requires Linux host kernel for
the `/dev/net/tun` device. macOS Docker Desktop runs a Linux VM, so
this works automatically there too.

**To stop:** `docker compose --profile tunnel-ts down`

## Listing your node in the federation seed list

Once your node is publicly reachable:

1. Edit `~/morm/docker/data/l1/seeds.json` (operator-mutable, read by
   `seed_loader.py` on every boot) to add yourself for *future* boots'
   self-discovery diff. Example:

   ```json
   {
     "version": 1,
     "updated_at": "2026-05-07",
     "seeds": [
       { "url": "https://morm.example.com",  "trusted_since": "2026-05-07", "owner": "you" }
     ]
   }
   ```

2. Open a PR against the upstream
   `morm-l1/morm_l1/seeds.json` to be included in the **baked-in** list
   that ships with future `ghcr.io/.../morm-l1` releases. We add seeds,
   never remove them — older nodes need to be able to trust the entries
   they were shipped with.

3. (Optional, future) If we agree on a `morm.network`-class shared zone,
   point the `discovery.dns_seed` SRV records at it. We deliberately do
   NOT do this today because the domain is not held by this project.

## Trust model

- The tunnel terminates TLS at Cloudflare or Tailscale's edge. Your
  node's HTTPS chain trusts whatever root cert ships with the browser.
  This is the same trust footprint as any web service hosted behind
  Cloudflare or Tailscale. No custom CA.
- The L1 chain consensus is independent of the tunnel — peers verify
  ed25519 block signatures locally regardless of where blocks come from.
- A misbehaving tunnel provider can DoS your node (drop requests) but
  cannot forge tx, blocks, or mint MORM. They can read browser-served
  HTML; for any tx the user does, the actual signing happens client-side
  via passkey + 2-of-2 XOR (Phase 7/9), so the tunnel sees only the
  encrypted-server-share of the seed and never the full key.
