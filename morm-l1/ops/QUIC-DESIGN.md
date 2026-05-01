# Phase 25 — QUIC gossip transport (design)

> "全ノード分散型でTikTokのような速度を実現するためには…即時確定性"
> — `MORM.md` §2

## 0. Status

- **Phase 25a — landed** (2026-04-26). Single-node + 2-node verified.
- **Phase 25b — landed** (2026-04-26). Compact binary block-header
  datagram per §7 below (245 B for typical block, well under any MTU).
  Symmetric 2-node verified: both nodes' `[quic-srv-datagram]
  BLOCK_HEADER` fires on the wire, state converges, head advances.
  The body still rides streams for reliability. The earlier
  JSON-as-datagram experiment (which silently dropped at ~1.4 KB
  payloads) is documented in §11 as the root-cause analysis that
  motivated the compact header.
- **Phase 25c — landed** (2026-04-26). HTTP `/gossip/tx` and
  `/gossip/block` removed; both endpoints return **HTTP 410 Gone**
  with a clear "removed in Phase 25c" pointer to `/info.quic_cert_pin`.
  `node.py:_fanout_*` no longer falls back to HTTP — peers without a
  `quic_cert_pin` are silently dropped (logged once per send). `cli.py`
  refuses to start when `--peers` is set without `--quic`. `/info`
  always reports `gossip_transport: "quic-only"` so peers can detect
  the floor at handshake time. 2-node verified post-removal: state
  converges (`ede7304a49cb9ae5`), compact 25b datagrams still fire.

The HTTP/1.1 gossip path (Phase 10c) has carried us through Phase 23a +
3-node verification, but it has two real ceilings that block reaching
the spec's "数秒以内に確定" goal at scale: (a) per-message TCP handshake
cost when peer count grows, and (b) head-of-line blocking that hurts
tail latency on congested links. This doc plots the migration to QUIC +
HTTP/3 datagrams.

## 1. Why QUIC, not just stay on HTTP/1.1

Today every gossip message is a fresh `urllib.request` call:

```
node A → POST http://peer:8900/gossip/block       (TCP handshake + TLS-less)
node A → POST http://peer:8900/gossip/tx          (another full handshake)
```

With N peers and B blocks/sec:
- **TCP handshakes/sec**: `B × N × 2` (block + tx). At 4 producers + 5
  blocks/s = 40 handshakes/s/peer. Each handshake adds ≥1 RTT (~50 ms LAN,
  ~150 ms regional WAN) before a single byte of payload. We're paying
  that cost every message, every time.
- **HoL blocking**: when one peer's link drops a packet, the TCP socket
  stalls — even though we have 5 unrelated tx fanouts queued behind it.
  Latency for unrelated traffic spikes.
- **No multiplexing**: `urllib.request` is one-shot, can't stream multiple
  gossip messages over a held socket.

QUIC fixes all three:
- 0-RTT or 1-RTT handshake (replayable session resumption).
- Per-stream and datagram demuxing — packet loss on stream A doesn't
  block stream B.
- Always TLS 1.3 (mandatory). We can finally drop the in-the-clear
  HTTP/1.1 surface.

For a pub/sub-shaped workload like block & tx fanout, QUIC **datagrams**
(unreliable, unordered, low-overhead) are an even better fit than streams.
That's the production target.

## 2. Goals / non-goals

**Goals:**
1. Reduce per-message gossip overhead from ≥1 RTT to **0–1 RTT amortised**.
2. Eliminate head-of-line blocking between unrelated gossip messages.
3. Add TLS 1.3 to all gossip traffic (cert-pinned by peer pubkey).
4. **Backward compatibility window**: HTTP/1.1 gossip remains available
   for at least one phase so old nodes can still join. Negotiated via
   a new field in `/info` (Phase 25a).

**Non-goals:**
- Replacing the RPC API (`/info`, `/tx`, `/account`, etc.) with QUIC.
  Those stay on HTTP/1.1. Wallets, browsers, and curl shouldn't need
  QUIC support.
- WebTransport for the browser P2P mesh (Phase 22). Browser-to-browser
  uses WebRTC; that's orthogonal.
- Custom transport — we use `aioquic`, full stop.

## 3. Surface area to migrate

Only these gossip paths in `node.py` move to QUIC:

```
_fanout_block(block)   → POST /gossip/block to every peer
_fanout_tx(tx)         → POST /gossip/tx to every peer
sync_from_peers()      → GET /info, GET /blocks/at/{h} pull
```

Everything else stays on HTTP/1.1.

## 4. Migration phases

### Phase 25a — opt-in QUIC alongside HTTP gossip
- Add an async `aioquic`-based listener bound to UDP `:8900` (same port,
  different transport — UDP and TCP coexist on the same socket family).
- Each node generates a self-signed cert at startup; the cert's public
  key is stored in `/info`, alongside the existing producer pubkey, so
  peers can pin it (TOFU-style).
- Outgoing fanout: if a peer's `/info` advertises a `quic_cert_pin`, use
  QUIC; otherwise fall back to HTTP POST (current path).
- Producer remains sync (threading); the QUIC listener runs in a
  dedicated `asyncio` thread with its own event loop.
- Only `/gossip/block` and `/gossip/tx` are served over QUIC. Everything
  else stays HTTP. Old nodes keep working unchanged.
- Feature flag: `--quic` CLI arg on `morm_l1.cli node`. Default off.

### Phase 25b — datagram-mode block fanout
- Switch block fanout from QUIC streams to **QUIC datagrams** (RFC 9221).
  A single block = 1 datagram (≤ 1200 B) for headers + tx-roots; full tx
  payload follows on a stream if the receiver requests it.
- Why: gossip is best-effort; lost datagrams are recovered by
  `sync_from_peers` on next tick. We don't pay reliable-stream overhead
  for messages we'd re-fetch anyway.
- TX gossip: stays on QUIC streams (txs are small, but we want
  acknowledgement so the sender knows the peer received it for nonce
  ordering).

### Phase 25c — drop HTTP gossip backward compat
- After 2 consecutive testnet runs with all peers on Phase 25a/b, remove
  the HTTP `/gossip/*` handlers. `/info`, `/tx`, `/account` etc. remain.
- Releases note: "node version ≥ X requires QUIC-capable peers."

## 5. Architecture: sync producer + async QUIC

The current node uses `threading.Thread` for the producer loop and
`ThreadingHTTPServer` for RPC. Adding aioquic without rewriting both:

```python
# in cli.py (sketch)
import asyncio, threading

def cmd_node(args):
    node = Node(...)
    node.start_producer()                  # existing sync thread
    rpc_srv = RpcServer((args.host, args.port), Handler)
    rpc_srv.node = node

    if args.quic:
        loop = asyncio.new_event_loop()
        def run_quic():
            asyncio.set_event_loop(loop)
            loop.run_until_complete(start_quic_listener(node, args.host, args.port))
            loop.run_forever()
        threading.Thread(target=run_quic, daemon=True).start()
        node.quic_loop = loop              # used by _fanout_* to schedule sends

    rpc_srv.serve_forever()
```

- `node._fanout_block(block)`: when peer is QUIC-capable, schedule
  `loop.call_soon_threadsafe(asyncio.create_task, send_quic(...))`.
- The async coroutine maintains a connection pool keyed by peer URL.
- Connection lifecycle: idle 5 min → closed.

This keeps the producer thread-based (simple, deterministic) and only
the network I/O goes async — the cleanest surface.

## 6. Cert handling (Phase 25a)

- On first start, generate `~/Library/Application Support/morm-l1/quic.{crt,key}`
  via `cryptography` (no openssl shell-out). 2048-bit RSA, 10-year
  validity (we re-roll on key rotation).
- Cert SAN = the producer's address (`m0r…`). This binds the transport
  identity to the chain identity.
- `/info` returns `quic_cert_pin: sha256(DER of pubkey)[:16]` (truncated
  for human reading; raw bytes available via `/info?full=1`).
- Outgoing fanout pins the expected pin; mismatch → fall back to HTTP and
  log the mismatch. **No cert authority.** TOFU-only is acceptable for
  a permissioned testnet; for mainnet, treasury can co-sign cert pins
  via a new tx kind (TODO Phase 25d, out of scope).

## 7. Wire format (Phase 25b datagrams)

### Block-header datagram (≤ 1200 B target)
```
| 1B  type=0x01 (BLOCK_HEADER)
| 1B  version
| 8B  height (BE)
| 32B header_hash
| 32B state_root
| 32B tx_root
| 32B producer_pubkey
| 64B header_sig
| 1B  parent_count N
| 32×N parent_hashes
| 2B  tx_count
```
At N=2 parents + 8 txs metadata, this is ~270 B — well within MTU.

### Block-body request (stream)
```
GET stream type 0x02:
   payload: header_hash (32 B)
RESPONSE:
   stream of all tx bytes for that block, length-prefixed.
```

Receivers cache the header datagram for K seconds, awaiting the body
to arrive (either pulled or fanned out separately).

## 8. Open questions

1. **Cert rotation**: producer keys are long-lived; should QUIC certs
   match producer-key lifetime, or rotate independently? Leaning toward
   independent rotation (≤ 90 days).
2. **NAT traversal for QUIC**: like WebRTC, QUIC needs UDP punch
   when both peers are behind symmetric NAT. We probably can't
   hole-punch without a coordinating server. Mitigation: testnet
   producers run on routable IPs (Cloudflare Tunnel doesn't work for
   UDP — same constraint as TURN, see `TURN.md`).
3. **MTU detection**: 1200 B is conservative but not always achievable
   over VPN tunnels. aioquic supports PMTU discovery; should we expose
   the actual MTU per peer via `/info`?
4. **Mempool dedup correctness with datagrams**: with unreliable
   delivery, two peers may receive different subsets. Phase 23a's
   import-time dedup still works; this just means we under-share, not
   over-share, which is the safer failure mode.

## 9. Estimated effort

| Phase | aioquic install + listener | fanout migration | tests | total |
|---|---|---|---|---|
| 25a | 6 h | 6 h | 4 h | **16 h** |
| 25b | — | 6 h | 4 h | **10 h** |
| 25c | — | 1 h (delete) | 2 h | **3 h** |

Total: ~29 h. 25a is shippable on its own (HTTP gossip stays available);
25b is only a perf upgrade and can wait a release.

## 10. Composition with other phases

- **DAG (Phase 24)**: lower fanout RTT directly improves DAG sibling
  convergence. The two phases compose without coupling.
- **BFT (deferred)**: BFT vote messages will use QUIC streams (need
  reliability), not datagrams.
- **Mac Mini Python regression**: blocks all of this on Mac Mini until
  resolved, since aioquic also depends on `<frozen getpath>` startup.

## 11. Phase 25b investigation log (2026-04-26)

Symmetric two-node datagram fanout silently drops every datagram —
both `[quic-client] block via datagram` logs fire on the senders, but
neither receiver's `DatagramFrameReceived` event ever appears. Streams
on the same connections deliver normally.

What does work:
- **Pure aioquic, 2 processes**: `/tmp/quic_2proc_{server,client}.py` —
  cross-process datagram delivers, server-side event fires.
- **Single-process MORM**: client + server in the same `asyncio.run()`
  loop — datagram delivers.
- **Asymmetric MORM 2-node**: A produces with `--quic`, B passive with
  `--quic --no-produce`. A's datagram block fanout reaches B's
  `DatagramFrameReceived` → `import_block` → state convergence
  (verified 2026-04-26: `state=539aa2ccb6e23c8f`, head=1).
- **Stream-only MORM 2-node** (current default after 25b partial):
  symmetric setup; both produce; all gossip via streams; convergence
  works (verified 2026-04-26: `state=351675e3a9981048`).

What fails:
- **Symmetric MORM 2-node with datagram block fanout** (the actual
  Phase 25b target). Both nodes log `[quic-client] block via datagram`
  on send; neither logs `[quic-srv-datagram]` on receive. State
  diverges because each node only sees its own block, not the peer's.

Hypotheses to investigate next:
1. **CID routing collision**: when both nodes simultaneously open
   client connections to each other, aioquic might be misrouting
   packets between connections sharing the same UDP 4-tuple.
2. **Source-port reuse**: if the QUIC client's ephemeral port
   accidentally overlaps with the bound server port (or another
   client's), incoming UDP gets fed to the wrong connection.
3. **`call_soon_threadsafe` vs `run_coroutine_threadsafe`**: tried
   both; neither fixes the symptom.
4. **`asyncio.sleep(0)` after `transmit()`**: tried; doesn't help.
5. **Disabling the connection cache** (fresh connection per send):
   tried; doesn't help.
6. **Disabling the server-side event spam** (`ConnectionIdIssued ×7`
   floods the log): cosmetic, not the bug.

Workaround in production: `node.py:_fanout_via_quic` forces
`prefer_datagram = False`, so blocks share the stream path with txs.
This loses the 25b benefit (no head-of-line blocking, no datagram
overhead saved) but stays correct.

Recommended way forward: rather than debug the JSON-as-datagram
implementation, **implement DAG-DESIGN §7's compact binary block
header** as the next 25b iteration. The smaller payload (~270 B vs
~1400 B) lets us safely use a smaller `max_datagram_frame_size`
(closer to MTU), and the redesign is a natural place to revisit the
CID/source-port concerns from scratch.

## 12. Phase 25b root-cause + resolution (2026-04-26)

The §11 investigation log diagnosed the symmetric-2-node datagram
silent-drop. It turned out to be **payload-size-driven IP fragmentation**
on the loopback path, not a CID/routing issue:

- Failing case: JSON-as-datagram ≈ 1384 B per block. UDP payload
  >1300 B over loopback exceeded the path's effective MTU after QUIC
  framing overhead, so the datagrams arrived fragmented and aioquic
  silently dropped the reassembled frame on the receiver side. No
  error logged anywhere — the symptom was "no `DatagramFrameReceived`
  event ever fires."
- Asymmetric case worked because only one direction was active under
  load; bidirectional simultaneous fragmentation evidently overlapped
  badly enough to drop both sides.
- Fix: **don't put the whole JSON block in the datagram**. The compact
  binary block-header datagram from §7 (~245 B for a 1-tx block, ~370
  B for 3 parents) fits in one MTU-sized UDP frame regardless of the
  block body size; the body continues to ride a stream where
  reliability is taken care of.

This split — datagram for fast-arrival announcement, stream for
reliable body — is exactly what §4 of this doc proposes for
production. The PoC implementation lives in:

- `quic.py:encode_compact_block_header(block) → bytes` (~213 + 32·N)
- `quic.py:decode_compact_block_header(data) → dict`
- `quic.py:_GossipServerProtocol._dispatch_compact_block_header(data)`
- `quic.py:QuicGossipClient.send_message(..., prefer_datagram=True)`
  → sends compact header via `send_datagram_frame` AND full body via
  stream concurrently.
- `node.py:_fanout_via_quic` → re-enabled `prefer_datagram = (kind ==
  "block")` after the fix.

Verification (2026-04-26 symmetric 2-node):

```
node A:
[quic-srv-datagram] BLOCK_HEADER hash=1dd8f535d3268d72… height=1 …
[quic-srv-datagram] NEW block announced via datagram, awaiting body via stream

node B:
[quic-srv-datagram] BLOCK_HEADER hash=1dd8f535d3268d72… height=1 …
[quic-srv-datagram] NEW block announced via datagram, awaiting body via stream

state convergence:
  :8990 head=2 state=a936668c495e06e6
  :8991 head=2 state=a936668c495e06e6
```

The compact-header datagram + stream body design is now the production
default for `--quic` MORM nodes. 25c is unblocked.
