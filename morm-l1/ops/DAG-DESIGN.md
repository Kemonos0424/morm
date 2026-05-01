# Phase 24 — true DAG parallelism (design)

> "全ノード分散型でTikTokのような速度を実現するためには、ビットコインのような
> 一本道の鎖ではなく、**DAG（有向非巡回グラフ）**のような並列処理構造が向いています。"
> — `MORM.md` §2

## 0. Status

This is a **design document**. No code is changed yet. Implementation is
scoped as Phase 24a–24d below; each phase is independently testable and
reversible. The current chain (Phase 17 + 23a) works; this doc plots the
path to making §2 of the spec real without breaking what's running.

## 1. Why DAG, why not just stay on Phase 17

Phase 17 (`slot_owner` deterministic election) gives a single-chain BFT
substrate: at every height exactly one producer is allowed to seal, all
others wait. With BLOCK_INTERVAL = 1 s and N producers, throughput is
capped at **1 block / second / network**, regardless of how many
producers join — adding nodes does not add throughput. That is the
opposite of what a global, viewing-dense network needs.

A DAG lets every producer seal independently when it has txs. With N
producers you get up to N× throughput at the same per-block latency, at
the cost of a more complex state-merge step. This is the standard
trade-off taken by Aleph-BFT, IOTA Tangle, Hashgraph, Avalanche-DAG,
Sui's Bullshark/Narwhal — MORM should sit in the same family.

## 2. Goals / non-goals

**Goals:**
1. Multiple producers seal blocks **simultaneously** without coordination.
2. **State convergence**: all honest nodes derive the same `state_root`
   for any given DAG frontier within a few seconds.
3. **No regression**: existing single-chain clients continue to work
   throughout the migration (Phase 24a–24c are backward-compatible).
4. **Spec-aligned finality**: "数秒以内に確定" (§2) — finality target
   ≤ 5 s end-to-end on a 3-region testnet.

**Non-goals (deferred to later phases):**
- Byzantine resistance to >½ producers — that's BFT, separate project.
- Sharding / parallel state machines per shard.
- Cross-DAG bridges between MORM L1 and other DAGs.

## 3. Current invariants (what we keep, what we change)

| Invariant | Phase 17 (today) | Phase 24 (target) |
|---|---|---|
| `Block.parent_hashes` | list, but `tip_hashes()` always returns 1 | list, regularly multi-element |
| `BlockHeader.height` | strict +1 from parent | `1 + max(parent.height)` (well-defined for DAG) |
| `BlockHeader.timestamp` | wall clock; deterministic via producer | unchanged |
| `BlockHeader.state_root` | computed after applying tx batch | computed after applying *merged* tx batch (§5) |
| `slot_owner(h)` | single producer per height | **removed** in 24c (replaced by per-producer rate limit) |
| Mempool | per-node deque, deduped on import (Phase 23a) | unchanged |
| Finality | head − K | "all current tips share an ancestor" (§6) |
| `state_root` invariant | identical across nodes | identical *for a given frontier* — frontier-relative |

The on-disk schema gains nothing new beyond what's already there (the
`parents` column in the `blocks` table is already a JSON array).

## 4. Migration phases

Each step is shippable and runs alongside the previous behaviour.

### Phase 24a — concurrent sealing (no slot election)
- `produce_one()`: drop the `slot_owner` check. Any registered producer
  may seal whenever its mempool is non-empty.
- `tip_hashes()`: return **all** blocks at the current max-height (already
  the SQL it does, but `produce_one` must use the result as multi-parent).
- New block: `parent_hashes = tip_hashes()`, `height = 1 + max(p.height)`.
- Same per-block tx ordering (the producer's mempool order); state_root
  computed from that single producer's apply path. Other producers may
  produce a sibling block at the same height with disjoint or overlapping
  txs.
- **Convergence is not yet guaranteed** — siblings can have different
  state_roots when they include different txs. Phase 24b fixes this.
- Test: 3 nodes, all producers, push 30 txs to each — verify each node
  produces ≥1 block per slot interval; verify the DAG is "wide" (multiple
  blocks per height).

### Phase 24b — frontier-relative state, canonical merge order
- Introduce **frontier**: the union of current tips, identified by the
  set of their hashes.
- Define the **canonical tx order** for a frontier:
  1. Walk the DAG from frontier toward genesis in BFS, collecting every
     tx not already applied in some ancestor common to all tips.
  2. Sort the collected txs by `(min(height_of_block_containing_tx),
     tx.hash())` — deterministic across nodes that see the same DAG.
  3. Apply in that order to genesis state.
  4. The resulting `state_root` is the **frontier_state_root**.
- `apply_block(block)`: no longer applies the block's tx batch directly.
  Instead, it (a) records the block in the DAG, (b) recomputes
  `frontier_state_root` for the new frontier, (c) verifies that
  `block.header.state_root == frontier_state_root_after_block_alone`.
  This means a sealed block stamps "this is the state if my txs alone
  were applied on top of my parent frontier" — every honest validator
  agrees on that, even if other concurrent siblings exist.
- The **node-level state_root** (what `/info` reports) is the
  frontier_state_root over all current tips, computed lazily.

### Phase 24c — finality via common-ancestor rule
- A DAG block is **finalized** when all current tips share it as an
  ancestor (transitive closure). This is the "GHOST common prefix" rule.
- Finalization triggers permanent state commit + `worker_stats` reward
  (matches existing reward semantics).
- Replace `FINALITY_DEPTH = 3` with `FINALITY_GAP = 2 levels of common
  ancestor with witness count ≥ ⅔ of registered producers`. Sketch:

  ```python
  def finalized_blocks(state):
      tips = state.tip_hashes()
      if len(tips) < ceil(2/3 * registered_producers):
          return []   # not enough witnesses
      return common_ancestors(tips)  # ordered, deepest-first
  ```

- `head_height` becomes `max(b.height for b in tips)`.
- `finalized_height` becomes `max(b.height for b in finalized_blocks(state))`.

### Phase 24d — per-producer rate limit + spam control
- Without slot election a malicious producer can spam blocks. Cap each
  producer's accepted seal rate to `R blocks / 10 s` where R = the
  producer's `weight` (currently `1 + worker_stats.completed`).
- Enforced in `import_block`: reject if the producer's last R blocks
  are all within the last 10 s window.
- This preserves §1 of the existing tokenomics (PoUW workers earn slot
  weight) without giving them a hard slot monopoly.

## 5. Tx-conflict semantics (the hard part)

When two producers concurrently include a tx that affects the same
account (e.g. two transfers from the same sender), only one can succeed
under the existing nonce check. The merge order in Phase 24b decides
which wins:

- **Same nonce, two siblings**: the tx with the **lower hash** wins
  (lexicographic on `tx.hash()`). The other becomes invalid in the merged
  state and is skipped during canonical replay.
- **Producer responsibility**: each producer's own block remains valid in
  isolation (its `state_root` is correct against its own parent
  frontier). The losing tx is simply **not applied** in the merged
  frontier. The producer is not penalized — they had no way to know.
- **No double-spend slips through**: the canonical replay applies txs in
  fixed order; account balance underflow is detected and the tx is
  skipped, exactly like Phase 17's `_apply_tx` rejection path.

For the gateway / wallet UX, this means a tx submitted twice via two
producers either lands once or not at all — never twice.

## 6. Wire format changes

Strict additions, no removals (24a–24c are wire-compatible with Phase
17 readers — they'll just see a "wider" chain than they expected):

| Field | Where | Notes |
|---|---|---|
| `parent_hashes` ≥ 2 entries | `Block.header` | already supported |
| `frontier_root` | new field on `/info` | hash of sorted tip-hash set; useful for sync coordination |
| `producer_rate_window` | new field on `/info` | per-producer recent-seal counts; used by 24d |
| `frontier_at` query | new RPC `GET /frontier?height=H` | returns the canonical tip set as of height H, for replay |

## 7. New invariants the test suite must enforce

```
∀ honest node N, tip set T ⊆ N.blocks:
  N.frontier_state_root(T) == M.frontier_state_root(T)   for any M with T

∀ block b sealed by node N:
  N.apply_block(b) succeeds ⇔ b.state_root ==
      apply(b.txs, frontier_state_root(b.parent_hashes))

∀ finalized block f:
  f appears in every honest node's `finalized_blocks` within Δ_finality
  (target Δ_finality ≤ 5 s on the testnet)
```

## 8. Open questions (need decision before 24c)

1. **Conflicting register-producer / register-ai-service / treasury txs**:
   if two producers race on a treasury-only tx with the same nonce, the
   lower-hash-wins rule applies. Is that acceptable, or should
   treasury-only txs go through a serialized "treasury slot" (essentially
   resurrecting Phase 17 for that subset)? Tentative answer: keep
   lower-hash-wins for simplicity; treasury can re-issue if their tx
   loses.

2. **State-root size growth**: Phase 24b recomputes `frontier_state_root`
   on each new tip. Worst case is O(|tip set| · |total txs since last
   common ancestor|) per tip. Need a cache + an incremental delta to
   avoid re-walking the whole DAG. Sketch: keep a `merge_cache` keyed by
   frozenset of tip hashes → state_root.

   → **Partially resolved (2026-04-30)** by Phase 24b throughput pass.
   Two cooperating caches now sit in `State`:
   - `_merge_cache: OrderedDict[frozenset, bytes]` (LRU 256 entries) —
     `frontier_hashes → state_root`. Only seeded for the no-extras path
     since extras vary per call.
   - `_materialized_frontier / _materialized_root` — track the frontier
     that the persistent db's derived tables currently reflect. Set
     post-COMMIT in `_apply_block_dag` (so concurrent readers never see
     a marker pointing at unpersisted state).

   With these in place `compute_frontier_state_root` and
   `replay_with_filter` take a **SAVEPOINT shortcut** when the requested
   frontier matches `_materialized_frontier`: open `BEGIN IMMEDIATE` on
   the persistent db, apply extras, read root, ROLLBACK. That skips the
   tempfile replica + genesis replay entirely (O(extras) instead of
   O(total ancestor txs)). The slow tempfile path remains for true DAG
   sibling cases where the requested frontier is not the materialized
   one.

   Incremental `_rebuild_materialized_state` for the linear /
   multi-tip-absorbing case is now also live (2026-04-30 follow-up):
   `_can_incremental_apply(block, new_tips)` accepts when
   `block.parents ⊆ old_materialized_frontier` AND
   `new_tips == (old_frontier - block.parents) ∪ {block.hash()}`.
   Then `_apply_block_incremental(c, block)` apply's the block's txs
   directly on the materialized state — `_canonical_tx_order` puts them
   last by canonical_height anyway, so this matches the full-rebuild
   result bit-for-bit. True DAG sibling cases (parents ⊄ old_frontier
   or a non-block new tip appears) still fall back to wipe+replay.

   Bit-for-bit equivalence is verified by the env-gated
   `MORM_FORCE_FULL_REBUILD=1` regression switch: same producer seed,
   same tx sequence, both paths compute identical state_roots
   (b33577a1…, afdf484b…, fcbaad80… across 3 waves of 30 transfers).

3. **Genesis bootstrap with 0 producers**: Phase 24a's "any node may
   produce" condition still needs the bootstrap path of the existing
   `slot is None` branch, otherwise a fresh testnet never produces its
   first block. Keep the existing escape hatch.

4. **Time-bounded mempool dedup window**: Phase 23a prunes the mempool
   on import, but with concurrent producers a tx might sit in mempool A
   while producer B already sealed it; A then re-includes it in its next
   block. The merge layer skips the dup, but mempool A still has it. Fix:
   when mempool dedup runs (Phase 23a code), also walk the DAG one level
   beyond the imported block to catch sibling-sealed txs.

## 9. Relation to other planned phases

- **BFT/finality** (separate phase, lower priority): Phase 24c gives
  honest-only finality. A 24c block is final iff ⅔ of producers built on
  top of it. To survive Byzantine producers we'd add a vote tx where
  producers explicitly attest to a tip; that's an orthogonal extension.
- **QUIC** (separate phase, lower priority): doubles down on §2's "数秒
  以内に確定" promise by lowering gossip RTT. Independent of 24a–24d but
  composes well — DAG fanout + QUIC datagram is the production target.
- **Sharding / multi-state** (out of scope here): once DAG is in, MORM
  can shard by content_id or producer_address with a small extension.

## 10. Estimated effort (per phase, dev hours)

| Phase | Code | Tests | Verification | Total |
|---|---|---|---|---|
| 24a | 4 | 2 | 2 | **8 h** |
| 24b | 12 | 6 | 4 | **22 h** |
| 24c | 8 | 4 | 4 | **16 h** |
| 24d | 4 | 2 | 2 | **8 h** |

Total: ~54 h. 24a is shippable on its own as a "concurrent producer
preview" without 24b's merge layer (state will diverge across siblings
but the DAG topology is observable for design validation).
