# Phase 22b — TURN server (coturn) for real-NAT WebRTC

Phase 22 wired browser-to-browser cell mesh over WebRTC, but only with STUN
(`stun:stun.l.google.com:19302`). STUN alone fails when both peers are behind
symmetric NAT (most home routers, mobile carrier NATs, corporate firewalls).
This phase adds an authenticated TURN server so peers can relay through it
when direct hole-punching fails, and serves the ICE config from the gateway
so the browser doesn't hard-code anything.

## Architecture

```
browser tab A ──┐                          ┌── browser tab B
                │   /api/signal/ice?…      │
                ├─────────────────────────►│
                │   (STUN + TURN urls,     │
                │    ephemeral creds)      │
                │                          │
                │   coturn :3478 (UDP/TCP) │
                └────────────────────────► relay (when STUN p2p fails)
```

The gateway never sees cell bytes — TURN relays are end-to-end opaque, only
ICE packets pass through. The gateway only signs short-lived credentials.

## What was added

- **`/api/signal/ice?peer_id=<hex>`** (passkey_morm.py): returns
  `{ ice_servers: [...] }` formatted for `RTCPeerConnection({iceServers})`.
- **CLI flags** on the gateway:
  - `--stun-url URL` (repeatable; default `stun:stun.l.google.com:19302`)
  - `--turn-url URL` (repeatable; e.g. `turn:host:3478?transport=udp`)
  - `--turn-secret HEX` — coturn `use-auth-secret` shared HMAC; gateway
    derives `username = "<expiry_unix>:<peer_id>"`,
    `credential = base64(HMAC-SHA1(secret, username))`. Default TTL 600s.
  - `--turn-cred-ttl SECONDS` (default 600)
  - `--turn-static-username` / `--turn-static-credential` for the rare
    static-creds case (one-off demos).
- **`morm-p2p.js`**: fetches ICE config at startup, refreshes every 5 min
  (creds expire every 10 min). HUD shows `iceMode = stun | turn |
  stun-fallback`. All `RTCPeerConnection` constructions read the latest
  `ICE_SERVERS` (both outgoing and incoming offers).
- **`ops/turn/turnserver.conf.template`** + **`install-coturn.sh`** —
  one-shot setup for macOS (Homebrew) or Linux (apt).

## Quick start (Mac Mini, LAN demo)

```bash
# 1) Install + configure coturn on the Mac Mini.
ssh user@<LAN-IP> \
  "cd ~/Desktop/MORM/morm-l1 && \
   ops/turn/install-coturn.sh --external-ip <LAN-IP> --realm morm.lan"
# It prints SHARED_SECRET — copy it.

# 2) Restart the gateway with TURN enabled.
cd ~/Desktop/MORM/morm-player
.venv/bin/python passkey_morm.py \
  --host 0.0.0.0 --port 8801 \
  --morm-rpc http://127.0.0.1:8900 \
  --treasury-seed <hex> \
  --turn-url 'turn:<LAN-IP>:3478?transport=udp' \
  --turn-url 'turn:<LAN-IP>:3478?transport=tcp' \
  --turn-secret <SHARED_SECRET>

# 3) Verify ICE config is being served.
curl -s 'http://localhost:8801/api/signal/ice?peer_id=test01' | jq
# Expect:
# {
#   "ice_servers": [
#     { "urls": "stun:stun.l.google.com:19302" },
#     { "urls": ["turn:<LAN-IP>:3478?transport=udp",
#                "turn:<LAN-IP>:3478?transport=tcp"],
#       "username": "1745611200:test01",
#       "credential": "abc...="
#     }
#   ]
# }

# 4) 2-tab verification (real browser, real machines preferred).
#    Tab A on MacBook Safari, Tab B on iPhone (over LAN or carrier).
#    Open http://<LAN-IP>:8801/player and select the same content.
#    HUD should show "P2P: 0 hits · 1 peers · turn" in both tabs.
#    Play a cell on A; B's HUD ticks "1 hits".
```

## Verifying TURN actually relays

`chrome://webrtc-internals` (Chrome) or `about:webrtc` (Firefox) →
look at the `selected-candidate-pair`. If it's `relay/relay`, TURN was
used. If `host/host` or `srflx/srflx`, STUN/direct sufficed.

For a server-side check, tail the coturn log:

```bash
brew services info coturn       # macOS
sudo journalctl -u coturn -f    # Linux
```

You should see `session ... realm=morm.lan` and `peer addr` lines while a
2-tab session is active.

## Public exposure (later)

For testnet over the internet:
1. Get a routable IPv4 (or IPv6) on the Mac Mini — Cloudflare Tunnel does
   **not** work for TURN (it's not HTTP). Options:
   - Static IP from ISP + port-forward 3478/udp,tcp + 5349/tcp + relay
     port range (e.g. 49160–49200/udp).
   - Tailscale + `tailscale serve` won't help either (TURN needs UDP).
   - Cheapest path: a $5 VPS (Hetzner/OVH) running coturn alongside the
     gateway tunnel, with the same `--turn-secret`.
2. Add a `cert-file` / `pkey-file` pair (Let's Encrypt) for `turns://`
   on 5349/tcp. Some corp networks only allow TLS to :443 — adding
   `tls-listening-port=443` lets you fall back to that.
3. Rotate `--turn-secret` periodically (it's a long-term shared secret;
   anyone with it can mint creds).

## Trade-offs / known limits

- **Bandwidth cost**: every relayed byte counts twice on the TURN server's
  uplink. A 4 MB cell relayed once = 8 MB of TURN traffic. Plan capacity.
- **Privacy**: TURN sees the *flow* (who talks to whom, how much) even
  though payload is opaque. Phase 23+ may add multi-TURN sharding and
  load-balancing for plausible deniability.
- **Per-peer creds**: we use `peer_id` as the userid in the HMAC. That's
  fine for accounting but means a leaked `peer_id` lets someone use TURN
  as that peer until expiry. Acceptable at PoC scale.
- **Preview iframes** (`localhost:5xxx`) cannot reach `192.168.x` UDP. Use
  real browser windows for end-to-end TURN verification.
