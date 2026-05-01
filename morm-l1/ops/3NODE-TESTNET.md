# Phase 23 — 3-node multi-producer testnet verification

Validates Phase 17 (multi-producer slot rotation + K-depth finality) end-to-end
with 3 independent producer processes on the same host (different ports). Same
algorithm as a 3-machine deployment; this isolation proves the consensus layer
without depending on physical-network reliability.

## What was verified

- **Convergence**: all 3 nodes hash identical `state_root` after 30 transfers
  (`f756a459cbca9470…`).
- **Finality**: head=32, finalized_height=29 (FINALITY_DEPTH=3, working).
- **Multi-producer slot rotation**: 2 distinct producers sealed blocks, picked
  by the deterministic `blake2b("morm-slot|"+height) % total_weight` election.
- **m0r-address transfer fix**: revealed and patched a Phase-18 oversight in
  `state.py:_tx_transfer` — recipient validation still required `0x` prefix.
  Now uses `crypto.parse_address()` to accept both m0r (native) and 0x (legacy).

## Phase 23a (mempool dedup-on-import) — landed

Initially the slot distribution was **A=23 / B=9 / C=0** for 32 blocks: C
sealed nothing because each node's mempool diverged after a peer sealed.
The fix in `node.py:import_block`:

```python
included = {tx.hash() for tx in block.transactions}
with self._lock:
    self.mempool = deque(
        tx for tx in self.mempool if tx.hash() not in included)
```

After re-running the same 30-tx load: **A=13 / B=11 / C=9** — within
statistical noise of perfectly uniform (11/11/11). Convergence + finality
(head=33, fin=30) preserved.

## Phase 24a (concurrent DAG sealing) — landed

Activated with `--dag-mode` on `morm_l1.cli node`. Drops the slot-election
gate in `produce_one`; relaxes the strict `state_root` match in
`apply_block` to skip-and-continue (sibling tx may already be applied).
Per `DAG-DESIGN.md` §4 24a, sibling state divergence is **tolerated**
until 24b lands frontier-relative state.

New `/info` fields:

- `dag_mode`        — bool, mirrors the CLI flag
- `dag_max_width`   — widest height in the chain so far (1 = single chain)
- `dag_head_width`  — number of tips at the current head height

Verification (3-node localhost full mesh, BLOCK_INTERVAL=0.05s, 3 senders
each blasting 150 transfers concurrently to its own node):

```
per-node snapshot:
  port=8910 head=  8 max_w=3 head_w=1 state_root=aac99818dc8ae2a0...
  port=8911 head=  8 max_w=3 head_w=1 state_root=aac99818dc8ae2a0...
  port=8912 head=  8 max_w=3 head_w=1 state_root=d5d3f6a091b2e056...

state_root: 2 distinct  (DAG-mode tolerates this; 24b will fix)

DAG topology (node A db):
  h=  4  2 block(s)  ██
  h=  5  3 block(s)  ███      ← every producer sealed concurrently
  h=  6  3 block(s)  ███
  h=  7  3 block(s)  ███
  total blocks=15, max_width=3
```

Both expected behaviours confirmed:

1. **DAG widens** to 3 sibling blocks at peak load — Phase 17's
   single-chain throughput cap is gone.
2. **State diverges** (8910/8911 vs 8912) because each producer applies
   its own tx batch onto its own current state, with no canonical merge
   yet. This is exactly the gap Phase 24b's frontier-relative state will
   close.

Reproduction:

```bash
# All 3 nodes started with --dag-mode + an aggressive BLOCK_INTERVAL.
MORM_BLOCK_INTERVAL=0.05 .venv/bin/python -m morm_l1.cli node \
  --data-dir /tmp/morm-3node/a --producer-seed $SEED_A \
  --treasury $TREAS_ADDR --port 8910 \
  --peers http://127.0.0.1:8911,http://127.0.0.1:8912 \
  --dag-mode &
# (B + C identical, swap seed/port)

# Load test (3 senders, 1 per node):
python /tmp/morm-3node/dag_load_test.py
```

## Phase 24b (frontier-relative state, canonical merge order) — landed

Activated alongside `--dag-mode`. State.py adds `_canonical_tx_order`
(BFS from frontier, sort by `(min_height, tx.hash())`),
`compute_frontier_state_root` (replay onto a fresh tempfile replica),
`replay_with_filter` (producer-side filter against canonical merged state),
`_rebuild_materialized_state` (wipe derived tables, replay onto persistent
db inside the import transaction), and `_apply_block_dag` (strict verify
that the producer's claimed state_root equals canonical(parents) +
block.txs). Node.py's `_produce_dag` reinserts un-applied txs back into
the mempool so nonce-gapped txs get a retry next round. RPC.py exposes
`frontier_root` on `/info` and a new `GET /frontier?height=H` for sync
coordination.

Verification (3-node localhost full mesh, BLOCK_INTERVAL=0.1s, 3 senders
each blasting 150 transfers concurrently to its own node):

```
per-node snapshot:
  port=8910 head=  5 max_w=3 head_w=3 state_root=37539dabaf81eda1... frontier=1a83dc01811e8244...
  port=8911 head=  5 max_w=3 head_w=3 state_root=37539dabaf81eda1... frontier=1a83dc01811e8244...
  port=8912 head=  5 max_w=3 head_w=3 state_root=37539dabaf81eda1... frontier=1a83dc01811e8244...

✓ state_root: ALL 3 CONVERGED  (37539dabaf81eda12ca3a2988280fa5f...)
✓ frontier_root: ALL 3 CONVERGED  (1a83dc01811e82440292556849048abf...)

DAG topology (node A db):
  h=  1  3 block(s)  ███
  h=  2  3 block(s)  ███
  h=  3  3 block(s)  ███
  h=  4  3 block(s)  ███
  h=  5  3 block(s)  ███
  total blocks=15, max_width=3
```

Both expected behaviours confirmed:

1. **DAG widens** to 3 sibling blocks at every height — concurrent
   sealing fully active.
2. **State converges** — every node computes the same canonical
   merged state from the same DAG. Phase 24a's divergence is closed.

A regression script for Phase 17 single-chain mode (`scenario_native.py`)
still passes 10/11 (test ④ `order_fee_split_99_1` was already querying
`/account/0xescrow` instead of the m0r-prefixed escrow account from Phase
18, unrelated to 24b — same ratio as pre-24b).

### Known throughput regression (deferred)

24b's `compute_frontier_state_root` rebuilds the full canonical state
from genesis via a tempfile sqlite replica on every block import + every
produce attempt. Cost is O(total ancestor txs) per call, and the
producer's BLOCK_INTERVAL=0.1s saturates well before the senders'
mempool drains under heavy load. SINK balance after 450 candidate
transfers: 4 (vs. ~450 with Phase 17 single-chain at the same load).
This is the **`merge_cache` optimization** flagged in DAG-DESIGN.md §8
open question 2 — keep a `frozenset(tip_hashes) → state_root` cache and
walk only the delta. Estimated ~6-10 h follow-up; not blocking the
correctness milestone.

## Phase 24c (common-ancestor finality) — landed

Replaces `head − FINALITY_DEPTH` rule for `--dag-mode` nodes. State.py
adds `_all_ancestors`, `common_ancestors(tips)`, and `finalized_height_dag`.
RPC `/info` reports `finalized_height` from `finalized_height_dag()` plus
a new `finality_rule` field naming the active rule (`"common-ancestor
(Phase 24c)"` or `"head − 3 (Phase 17b)"`). Witness threshold:
`⌈2/3 × N_registered_producers⌉` tips required, otherwise finalization
freezes (returns 0).

Verification (3-node localhost full mesh, BLOCK_INTERVAL=0.5s, 3 senders
× 5 transfers each):

```
  :8910  head=  4 fin=  3 rule= common-ancestor (Phase 24c) state= d8d71396e9c2ece6 frontier= 2d24ec41fbf50353 max_w= 3
  :8911  head=  4 fin=  3 rule= common-ancestor (Phase 24c) state= d8d71396e9c2ece6 frontier= 2d24ec41fbf50353 max_w= 3
  :8912  head=  4 fin=  3 rule= common-ancestor (Phase 24c) state= d8d71396e9c2ece6 frontier= 2d24ec41fbf50353 max_w= 3
```

`finalized = head − 1` (vs. Phase 17 `head − 3`) because every tip at
height H builds on every height-(H−1) sibling block, so the entire
height-(H−1) layer is a common ancestor of all current tips.

### Pre-existing bug surfaced + fixed

While verifying 24c, persistent state diverged across nodes (live
state_root differed even though canonical replay produced the same root
on every db). Root cause: `state.py:get_account` called `_ensure_account`
on every read, so any `/account/<addr>` HTTP query INSERTed a zero-row
into `accounts`. Single-chain Phase 17 absorbed this silently because
state_root only had to match within a node, but Phase 24b's
materialized-state-equals-canonical-replay invariant exposes it as a
3-way divergence. Fix: `get_account` is now read-only (returns zeros for
unknown addresses without creating a row). Bug predates Phase 11d.

## Phase 24d (per-producer rate limit + spam control) — landed

State.py exposes `_producer_weight` (= `1 + worker_stats.completed`),
`_producer_seal_count_in_window`, `producer_rate_limit_ok(block)`, and
`producer_rate_window()` (operator introspection). `_apply_block_dag`
gates every block on the rate cap before the expensive 24b verify, so
both gossip imports and self-produced blocks honour the limit. `/info`
adds a `producer_rate_window` field listing each registered producer's
current `recent_seals` and `weight_R`. Window size:
`State.PRODUCER_RATE_WINDOW_MS = 10_000` ms.

Single-node verification (8920, 1 producer registered, R=1):

```
block 1 ts = 1777165653178   (register tx sealed)
block 2 ts = 1777165663182   (5 transfers in mempool sealed after wait)
gap        = 10004 ms        ← exact 10s rate window enforced
```

3-node DAG verification (BLOCK_INTERVAL=0.5s, 3 producers each R=1,
3 senders × 5 transfers = 15 transfers + 3 funding + 3 register-producer
txs, 26s total wait):

```
  :8910 head=4 fin=3 state=8f68c93ec1205a71 max_w=3
        node-a: R=1 recent=0
        node-b: R=1 recent=0
        node-c: R=1 recent=0
        SINK balance = 15            ← all 15 transfers landed

  :8911 head=4 fin=3 state=8f68c93ec1205a71 max_w=3   (identical)
  :8912 head=4 fin=3 state=8f68c93ec1205a71 max_w=3   (identical)
```

Three behaviours simultaneously confirmed:

1. **Rate limit enforced** — each producer caps at R=1 block per 10 s
   without PoUW credit; higher weights would proportionally raise the
   cap.
2. **DAG widening preserved** — max_w=3 unchanged; rate limit caps
   per-producer, not global throughput.
3. **State convergence + finality + tx liveness intact** — every node
   ends with the same state_root, every funded transfer lands.

### Pre-existing canonical sort bug surfaced + fixed

While verifying 24d the burst register-producer flow exposed a `_canonical_tx_order`
shortcoming: the spec's `(height, tx.hash())` sort doesn't preserve
nonce ordering for multiple txs from the same sender at the same
canonical height. Treasury's 3 register txs (nonces 0, 1, 2) sorted
by tx.hash put nonce=2 first, which fails the nonce check, and
canonical replay skipped half of them. Fix: sort key extended to
`(height, sender, nonce, tx_hash)` — strict refinement, deterministic,
addresses DAG-DESIGN.md §8 open question 1 explicitly. Same bug would
have affected viewer-reward bursts and any multi-tx-per-sender pattern;
exposed only because 24d slowed sealing enough to batch the registers
into one canonical block.

Also: `_produce_dag` now re-inserts the `applied` txs back into the
mempool when the producer's own self-apply fails (e.g. rate-limit
rejection). Without this, a rate-limited producer silently dropped
every tx it had drained for the failed seal.

## Phase 25a (QUIC opt-in gossip transport) — landed

aioquic 1.3.0 in venv. New module `morm_l1/quic.py`: self-signed
RSA-2048 cert generation under `<data_dir>/quic.{crt,key}` (idempotent;
SAN = producer m0r-address), SPKI pin (`sha256(DER pubkey)[:16]` hex,
TOFU), `_GossipServerProtocol` (per-stream length-prefixed JSON dispatch
to `Node.import_block` / `Node.submit_tx`), `QuicGossipClient`
(per-peer connection cache, idle timeout 5 min), and `QuicRuntime` (own
asyncio thread; sync producer/RPC unchanged). `node.py:_fanout_*` now
hybrid: peers advertising `quic_cert_pin` in `/info` get QUIC, rest stay
on HTTP. `cli.py --quic` enables, default off.

2-node verification (8940/8941, both `--quic --dag-mode`,
BLOCK_INTERVAL=1s, treasury sends 2 register-producer txs):

```
=== node A log ===
[quic] listener up on udp://127.0.0.1:8940
[quic-fanout] tx → http://127.0.0.1:8941 (pin=320f0a9a0784754e)
[quic-fanout] tx → http://127.0.0.1:8941 (pin=320f0a9a0784754e)
[quic-fanout] block → http://127.0.0.1:8941 (pin=320f0a9a0784754e)

=== node B log ===
[quic] listener up on udp://127.0.0.1:8941
[quic-fanout] block → http://127.0.0.1:8940 (pin=502e9e6ceff09043)

=== final ===
  :8940 head=1 state=12185e2bd1524dd6 producers=2
  :8941 head=1 state=12185e2bd1524dd6 producers=2
```

State convergence preserved; 4 messages confirmed via QUIC streams (the
HTTP fallback was never exercised since both peers advertised pins).

Backward compatibility: nodes without `--quic` see no change — they
gossip via HTTP as before. A QUIC-enabled node mixed with HTTP-only
peers transparently uses HTTP for those peers.

## What is still NOT verified

- **Cross-machine WAN latency**: this verification was localhost. Actual LAN
  / WAN gossip is exercised separately by the existing `invite-node.sh` flow.
- **Adversarial slot collisions**: only happy-path producers; no equivocation
  / fork-choice tested. That belongs in BFT (separate Phase, post-24d).
- **24b throughput** — see "Known throughput regression" above.
- **24c under partition**: when concurrent tips drop below ⌈⅔ N⌉ witnesses
  (e.g. one producer offline in a 2-of-3 split), finality should freeze.
  Frozen-and-resume behaviour not yet tested with deliberate fault injection.
- **24d weight scaling**: only verified at R=1 (no PoUW). Higher R via
  worker_stats.completed not exercised.
- **25a 3-node QUIC**: 2-node verified; extending to 3-node mesh + WAN
  not yet exercised. Pin-mismatch / cert-rotation paths also untested.
- **25b/c (datagrams + HTTP gossip removal)**: design-only; not implemented.

## Reproduction (script template)

```bash
DATA=/tmp/morm-3node && rm -rf $DATA && mkdir -p $DATA/{a,b,c}
cd ~/Desktop/MORM/morm-l1
SEED_A=$(.venv/bin/python -m morm_l1.cli keygen | python3 -c "import json,sys;print(json.load(sys.stdin)['seed_hex'])")
SEED_B=$(.venv/bin/python -m morm_l1.cli keygen | python3 -c "import json,sys;print(json.load(sys.stdin)['seed_hex'])")
SEED_C=$(.venv/bin/python -m morm_l1.cli keygen | python3 -c "import json,sys;print(json.load(sys.stdin)['seed_hex'])")
SEED_TREAS=$(.venv/bin/python -m morm_l1.cli keygen | python3 -c "import json,sys;print(json.load(sys.stdin)['seed_hex'])")
TREAS_ADDR=$(.venv/bin/python -c "from morm_l1 import crypto; s=bytes.fromhex('$SEED_TREAS'); print(crypto.address(crypto.pubkey_from_seed(s)))")

# Full mesh — every node lists the other two as peers so fanout reaches all.
.venv/bin/python -m morm_l1.cli node --data-dir $DATA/a --producer-seed $SEED_A --treasury $TREAS_ADDR --port 8910 --peers http://127.0.0.1:8911,http://127.0.0.1:8912 &
.venv/bin/python -m morm_l1.cli node --data-dir $DATA/b --producer-seed $SEED_B --treasury $TREAS_ADDR --port 8911 --peers http://127.0.0.1:8910,http://127.0.0.1:8912 &
.venv/bin/python -m morm_l1.cli node --data-dir $DATA/c --producer-seed $SEED_C --treasury $TREAS_ADDR --port 8912 --peers http://127.0.0.1:8910,http://127.0.0.1:8911 &
sleep 3

# Register all three as producers via treasury REGISTER_PRODUCER tx.
# (See /tmp/morm-3node/register.py from the verification session.)

# Send N transfers, then poll /info on each node — all 3 must report the
# same state_root and head_height; finalized_height = head - 3.
```

## Architectural note: mempool sync (deferred)

Currently `Node.mempool` is a per-process deque cleared by `drain_mempool()`.
For balanced multi-producer load the import path needs:

```python
def import_block(self, block: Block, gossip: bool = True) -> bool:
    # ... existing apply ...
    with self._lock:
        included = {tx.hash() for tx in block.transactions}
        self.mempool = deque(t for t in self.mempool if t.hash() not in included)
```

This is a 3-line change but introduces `tx.hash()` requirement on the
Transaction class — left for Phase 23a.
