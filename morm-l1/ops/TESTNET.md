# MORM Testnet — Public Network Setup

## Overview

A MORM testnet is just one or more bootstrap nodes reachable over the
internet, plus an open invitation channel. There's no token sale, no
genesis ceremony — every state is rebuildable from genesis seed +
treasury seed + accepted txs.

**Roles**

| Role | Function | Hardware |
|---|---|---|
| Bootstrap | RPC at a stable address; new joiners pull `/bootstrap` | always-on, public IP |
| Producer | Sealed slots in the rotation; weight = 1 + jobs done | always-on |
| Edge / Mirror | `morm-player/server.py` for video distribution | any |
| Light | Browser identity → MORM L1 RPC | none |

## 1. Open the bootstrap node to the internet

Three reasonable options on macOS:

### A. Cloudflare Tunnel (recommended — TLS, zero firewall)

```bash
brew install cloudflared
cloudflared tunnel login                       # one-time, browser auth
cloudflared tunnel create morm-bootstrap
cloudflared tunnel route dns morm-bootstrap rpc.morm.example
cat > ~/.cloudflared/config.yml <<EOF
tunnel: morm-bootstrap
credentials-file: ~/.cloudflared/<UUID>.json
ingress:
  - hostname: rpc.morm.example
    service: http://127.0.0.1:8900
  - service: http_status:404
EOF
cloudflared tunnel run morm-bootstrap &        # or LaunchAgent
```

→ Anyone can `curl https://rpc.morm.example/bootstrap` from anywhere.

### B. Tailscale Funnel (private testnet)

```bash
brew install tailscale
sudo tailscale up
sudo tailscale funnel 8900
```

→ A `https://<machine>.<ts-net>.ts.net/` URL becomes reachable on the
public internet, but only via Tailscale's CDN. Cheap + lazy.

### C. ngrok (one-shot demo)

```bash
brew install ngrok
ngrok http 8900
```

Copy the `https://….ngrok-free.app` host — short-lived but instant.

## 2. Invite a new producer

From the bootstrap host (which has `morm-l1/` checked out and treasury
keys at `/tmp/k_treas.json`):

```bash
cd ~/Desktop/MORM/morm-l1
ops/invite-node.sh user@new-host.example --name "alpha-osaka"
```

The script:

1. checks Python 3.11+ and ffmpeg on `new-host`
2. rsyncs `morm-l1/` to `new-host:~/MORM/morm-l1/`
3. creates a venv with `cryptography`
4. generates a fresh ed25519 producer key on `new-host`
5. installs a LaunchAgent (macOS) or systemd unit (Linux) pointing to
   the bootstrap host
6. submits a treasury-signed `REGISTER_PRODUCER` tx so the new node
   enters the slot rotation

After ~5 seconds the new producer should appear in
`https://rpc.morm.example/info` under `producers` with `weight: 1`.

## 3. Bootstrap discovery contract

Any new node hitting **`GET /bootstrap`** receives:

```json
{
  "self":     "http://127.0.0.1:8900",
  "peers":    ["http://127.0.0.1:8900"],
  "treasury": "m0r3or65m6jbnlb6fnd2nvylah23vo54dky",
  "finality_depth": 3,
  "head_height": 12,
  "registered_producers": 3
}
```

This is the public chain identity. Light clients should treat the
bootstrap response as the source of truth for `treasury` and bootstrap
peers (i.e. it's the equivalent of an Ethereum chain-spec).

## 4. Browser-side configuration

The hosted Admin UI at `https://rpc.morm.example/admin` (when the
passkey gateway is also tunneled) embeds:

- network state (head/finalized/treasury/state_root/tips)
- registered producers list with weights
- "Generate invite" command

For multi-host testnet, run one **passkey gateway** + multiple **L1
producers**. Browsers connect to the gateway over HTTPS, the gateway
brokers `morm-tx` to its local L1, and gossip propagates to peers.

## 5. Operational notes

- **Never commit the treasury seed** into the public repo. Distribute
  it via `tmp/` or a CI secret store.
- **Rotate** the treasury seed: set up a fresh chain (genesis), have the
  new treasury pre-issue `REGISTER_PRODUCER` txs for the trusted set,
  then publish `/bootstrap` as canonical.
- **Slashing** is currently treasury-only (Phase 4/10d). Add a quorum
  of validators (Phase 13b multi-sig) before any external value flows.
- **Multi-sig bridge** (`MORMBridgeMS.sol`) and **challenge window**
  (`MORMBridgeOptimistic.sol`) should be the deployed bridges before
  any real-value EVM funds are accepted.

## 6. End-to-end smoke test (3 hosts)

```bash
# host A (you):
cd ~/Desktop/MORM/morm-l1
ops/install-launchd.sh "$(jq -r .seed_hex /tmp/k_prod.json)" \
                       "$(jq -r .address /tmp/k_treas.json)"

# host B + C: from host A
ops/invite-node.sh user@host-b --name beta
ops/invite-node.sh user@host-c --name gamma

# verify rotation (each producer should seal ≥1 block within 30s)
sleep 30
curl https://rpc.morm.example/blocks/latest?n=20 | jq '.blocks[].producer' | sort | uniq -c
```

Expected: roughly proportional to `weight`. With three producers all at
weight 1, expect ~33% / 33% / 33% over a long window.
