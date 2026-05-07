# MORM

Federated video SNS with **walletless passkey identity**, an **ed25519 DAG L1 chain**, and a **multi-currency EVM bridge**. Mobile-first portrait HLS feed (TikTok-style), camera-first creator UX, per-segment view rewards, M-of-N quorum bridge.

> **Honest about prior art (3 principles)**: MORM is a *composition* of existing primitives — passkeys (FIDO2/WebAuthn), 2-of-2 secret sharing, ed25519 chains (cf. Solana/Tezos/Near), federated bridges, DAG ledgers. The contribution is integration + a no-LLC, no-privileged-registry stance.

## Status

**69 Phase complete** (2026-05-02). End-to-end loop: portrait camera upload → HLS encode → on-chain registration → mobile scroll-snap viewer → per-segment passkey-signed VIEW_REWARD → wallet policy gate → optional ETH/USDC swap via /swap. See [`docs/IMPLEMENTATION-STATUS.md`](docs/IMPLEMENTATION-STATUS.md) for the full Phase ↔ implementation map.

## Run a federated node (Docker)

> ⚠️ **First-time setup note**: as of v0.1.0 the ghcr.io images for this
> repo were initially private (GitHub default). If pulls require auth,
> the maintainer needs to flip each image to public: GitHub → `Your
> profile` → `Packages` → `morm-l1` / `morm-gateway` / `morm-edge` →
> `Package settings` → `Change visibility` → `Public`. Until then,
> install.sh falls back to a local `docker compose build` and works the
> same way (just slower the first time).

```bash
curl -fsSL https://raw.githubusercontent.com/Kemonos0424/morm/main/docker/install.sh | bash
```

This will:

1. Verify Docker + Compose are installed
2. Clone the repo to `~/morm` (override with `MORM_DIR=...`)
3. Generate fresh producer + treasury ed25519 keys (`docker/init.sh`)
4. Pull (or locally build) the `morm-l1`, `morm-gateway`, `morm-edge` images
5. Bring up the compose stack (ports 8900 / 8801 / 8787)
6. Print the `/auth-morm`, `/wallet`, `/swap` URLs

To stop:

```bash
cd ~/morm
docker compose -f docker/morm-node.docker-compose.yml down
```

## Public ingress (optional)

If you're behind a NAT and want your node reachable from the public
internet (so others can use your `/auth-morm`, `/swap`, etc.), enable
one of the two opt-in tunnel sidecars:

```bash
# Cloudflare Tunnel (free with any domain on Cloudflare DNS):
docker compose -f docker/morm-node.docker-compose.yml --profile tunnel-cf up -d

# Or Tailscale Funnel:
docker compose -f docker/morm-node.docker-compose.yml --profile tunnel-ts up -d
```

Setup steps and trust-model notes:
[`morm-l1/ops/PUBLIC-INGRESS.md`](morm-l1/ops/PUBLIC-INGRESS.md).

Only the gateway service (port 8801, browser-facing) is published. The
L1 RPC and Edge stay private inside the compose network.

## Federation

Each node ships with a baked-in seed list (`morm-l1/morm_l1/seeds.json`, append-only). On boot, [`seed_loader.py`](morm-l1/morm_l1/seed_loader.py) merges:

1. `--peers` (CLI override)
2. `<data-dir>/seeds.json` (operator's own additions)
3. baked-in `seeds.json` (release-frozen)
4. live discovery (DNS SRV / GitHub raw / IPFS — operator-configured)

No single DNS zone or registry is in the trust path. Nodes find each other through any of the four channels. See [`morm-l1/ops/BRIDGE-DESIGN.md`](morm-l1/ops/BRIDGE-DESIGN.md) §5 for the bridge-side validator federation design.

## Architecture (one screen)

```
┌───────────── browser ──────────────┐
│  /auth-morm  /upload  /player-hls  │  passkey, ed25519 sign
│  /wallet     /shop    /swap        │  (no extension required)
└──────┬─────────────────────────────┘
       │ http
┌──────▼────── gateway 8801 ────────┐
│ passkey + 2-of-2 XOR seed + HLS  │
│ encode + bridge UI + tx confirm  │
└──────┬─────────────────────────────┘
       │ http
┌──────▼────── L1 8900 ──────────────┐  HLS storage 8787
│ ed25519 / DAG / sqlite / QUIC opt  │  Edge (origin or mirror,
│ blocks, mempool, treasury multisig │  P2P .m4s mesh between
└──────┬─────────────────────────────┘  viewers)
       │ EVM JSON-RPC
┌──────▼─────── Anvil / Mainnet ─────┐
│ MORMBridge / MORMBridgeERC20 /     │
│ MORMBridgeMS (Echidna 4/4 PASS)    │
└────────────────────────────────────┘
```

## Repo layout

```
morm-l1/         L1 chain (cli, node, state, tx, crypto, quic, seed_loader)
morm-core/       HLS encoder + WebM cell + screening + V-Hash
morm-player/     gateway + edge + browser static (auth, upload, player-hls,
                 wallet, shop, swap, morm-i18n, morm-guide, morm-policy, ...)
morm-chain/      Solidity (MORMBridge / MORMBridgeERC20 / MORMBridgeMS /
                 MORMBridgeOptimistic / MORMEscrow), Foundry tests, Echidna
morm-aiservice/  AI service registration (Phase 14)
docker/          Dockerfiles (3) + compose + entrypoints + init.sh + install.sh
docs/            Whitepaper (ja/en), IMPLEMENTATION-STATUS, prior-art notes
.github/workflows/   ghcr.io multi-arch publish
relayer.py       Single-key bridge relayer (PoC; see Phase 13b for M-of-N)
scenario_*.py    End-to-end smoke tests (native, swap, swap_usdc, swap_quorum, …)
```

## Documentation

- [Implementation Status (Phase ↔ code map)](docs/IMPLEMENTATION-STATUS.md) — single source of truth for what's built
- [Whitepaper (ja)](docs/ja/WHITEPAPER.md) / [Whitepaper (en)](docs/en/WHITEPAPER.md)
- [Bridge design (Phase 28 + 13b)](morm-l1/ops/BRIDGE-DESIGN.md)
- [Phase 25-Video (HLS pipeline)](docs/PHASE25-VIDEO.md)
- [Security threat model](morm-l1/ops/SECURITY-DESIGN.md)
- [DAG / QUIC / TURN design notes](morm-l1/ops/) — DAG-DESIGN.md, QUIC-DESIGN.md, TURN.md
- [Manifesto (ja)](docs/ja/MANIFESTO.md) — the why

## License

MIT (see [LICENSE](LICENSE) — to be added).

## Contributing

This is a research-grade PoC; production deployment requires (at minimum) Phase 13b's full M-of-N relayer migration, Phase 29's multi-passkey + recovery UX, and a dedicated audit pass. Issues + PRs welcome via GitHub. There is no LLC behind this repo; mirrors and forks are encouraged.
