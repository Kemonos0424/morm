"""Chain state machine — applies transactions to a SQLite-backed key-value store.

The schema mirrors the EVM contract from Phase 4 but lives natively on the
chain (no Solidity execution). State changes go through `apply_tx`, which
is also where business rules live (1% fee, generation_id uniqueness, etc.).
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

from . import crypto
from .tx import Transaction, TxKind

FEE_BPS = 100         # 1.0%
BPS_DENOM = 10000

# Synthetic escrow account — deterministically derived from a label so every
# node lands on the same string without needing a registry tx.
def _synthetic_addr(label: str) -> str:
    raw20 = hashlib.blake2b(label.encode(), digest_size=32).digest()[-20:]
    import base64 as _b
    return "m0r" + _b.b32encode(raw20).decode().lower().rstrip("=")

ESCROW_ACCOUNT = _synthetic_addr("morm-escrow")
VIEW_REWARD_AMOUNT = 1   # 1 base-unit MORM per uniquely-watched cell

SCHEMA = """
CREATE TABLE IF NOT EXISTS contents (
    content_id    TEXT PRIMARY KEY,
    root_hash     TEXT NOT NULL,
    generation_id TEXT,
    creator       TEXT NOT NULL,
    registered_at INTEGER NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_gen_id_unique
    ON contents(generation_id) WHERE generation_id IS NOT NULL;

-- registry of AI service identities allowed to issue Generation IDs.
-- Treasury adds/removes via REGISTER_AI_SERVICE / REVOKE_AI_SERVICE tx.
CREATE TABLE IF NOT EXISTS ai_services (
    pubkey      TEXT PRIMARY KEY,    -- ed25519 pubkey hex (64 chars)
    name        TEXT NOT NULL,
    registered_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS orders (
    order_id      TEXT PRIMARY KEY,
    content_id    TEXT NOT NULL,
    buyer         TEXT NOT NULL,
    seller        TEXT NOT NULL,
    amount        INTEGER NOT NULL,    -- 99% locked
    fee           INTEGER NOT NULL,    -- 1% paid to treasury
    packing_hash  TEXT,
    opening_hash  TEXT,
    status        INTEGER NOT NULL,    -- 1=Created 2=PackingDone 3=OpeningDone 4=Finalized 5=Refunded
    created_at    INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS accounts (
    address  TEXT PRIMARY KEY,
    nonce    INTEGER NOT NULL DEFAULT 0,
    balance  INTEGER NOT NULL DEFAULT 0,
    stake    INTEGER NOT NULL DEFAULT 0,
    locked   INTEGER NOT NULL DEFAULT 0
);

-- bridge ledger: tracks both directions of the EVM ↔ MORM swap.
CREATE TABLE IF NOT EXISTS bridge_mints (
    evm_lock_id TEXT PRIMARY KEY,    -- source EVM event id (chain:tx:log)
    recipient   TEXT NOT NULL,
    amount      INTEGER NOT NULL,
    minted_at   INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS bridge_burns (
    burn_tx_hash  TEXT PRIMARY KEY, -- the L1 tx hash that did the burn
    burner        TEXT NOT NULL,
    amount        INTEGER NOT NULL,
    evm_recipient TEXT NOT NULL,
    token         TEXT NOT NULL DEFAULT 'MORM',  -- 'MORM' = native ETH-bridged; else ERC-20 symbol
    token_address TEXT,                          -- EVM contract address for ERC-20 (optional)
    evm_unlocked  INTEGER NOT NULL DEFAULT 0,
    burned_at     INTEGER NOT NULL
);

-- ERC-20 token balances on the L1. Native MORM stays in accounts.balance;
-- bridged ERC-20s (USDC, etc.) live here keyed by token symbol.
CREATE TABLE IF NOT EXISTS account_tokens (
    address TEXT NOT NULL,
    token   TEXT NOT NULL,        -- 'USDC', etc.
    balance INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (address, token)
);

-- per-cell view rewards. UNIQUE so the same viewer+cell can't double-claim.
CREATE TABLE IF NOT EXISTS views (
    viewer       TEXT NOT NULL,
    content_id   TEXT NOT NULL,
    cell_index   INTEGER NOT NULL,
    rewarded_at  INTEGER NOT NULL,
    PRIMARY KEY (viewer, content_id, cell_index)
);

-- PoUW: jobs are bounties to perform "useful work" — encoding, AI tagging,
-- moderation, etc. The poster locks a reward; a worker claims and submits a
-- proof (output_root); the chain releases the reward.
CREATE TABLE IF NOT EXISTS jobs (
    job_id      TEXT PRIMARY KEY,
    content_id  TEXT NOT NULL,
    kind        TEXT NOT NULL,         -- 'transcode' | 'tag' | 'moderate' | …
    poster      TEXT NOT NULL,
    reward      INTEGER NOT NULL,
    claimer     TEXT,                  -- worker address (set on CLAIM_JOB)
    output_root TEXT,                  -- set on SUBMIT_WORK_PROOF
    status      INTEGER NOT NULL,      -- 1=Posted 2=Claimed 3=Completed
    posted_at   INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_jobs_status   ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_claimer  ON jobs(claimer);

-- worker reputation = # of completed jobs. Used in 10b-onward as input to
-- producer election ("more useful work → more chance to lead a block").
CREATE TABLE IF NOT EXISTS worker_stats (
    address    TEXT PRIMARY KEY,
    completed  INTEGER NOT NULL DEFAULT 0,
    earned     INTEGER NOT NULL DEFAULT 0
);

-- Phase 17a: registered producers. Treasury whitelists pubkeys; each block's
-- "slot owner" is chosen by hash(seed||height) % total_weight, where weight
-- = 1 + worker_stats.completed (PoUW-driven).
CREATE TABLE IF NOT EXISTS producers (
    pubkey  TEXT PRIMARY KEY,        -- 32-byte ed25519 pubkey hex
    address TEXT NOT NULL,
    name    TEXT NOT NULL,
    registered_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS blocks (
    hash         TEXT PRIMARY KEY,
    height       INTEGER NOT NULL,
    parents      TEXT NOT NULL,        -- json array of hex hashes
    producer     TEXT NOT NULL,
    state_root   TEXT NOT NULL,
    payload      TEXT NOT NULL         -- full block json
);
CREATE INDEX IF NOT EXISTS idx_blocks_height ON blocks(height);

-- Phase 26a: treasury multi-sig (M-of-N).
-- treasury_signers holds the N pubkeys allowed to cosign treasury-only
-- txs once multi-sig is active.
CREATE TABLE IF NOT EXISTS treasury_signers (
    pubkey         TEXT PRIMARY KEY,    -- ed25519 pubkey hex (64 chars)
    name           TEXT NOT NULL,
    registered_at  INTEGER NOT NULL
);
-- treasury_config is a single-row settings table. `enabled=1` flips the
-- gate that rejects single-key BRIDGE_MINT/FINALIZE/REGISTER_PRODUCER/
-- REGISTER_AI_SERVICE; from then on those kinds must be wrapped in
-- MULTISIG_TX with >= threshold signatures.
CREATE TABLE IF NOT EXISTS treasury_config (
    rowid       INTEGER PRIMARY KEY CHECK (rowid = 1),
    threshold   INTEGER NOT NULL,
    n_signers   INTEGER NOT NULL,
    enabled     INTEGER NOT NULL DEFAULT 0,
    enabled_at  INTEGER
);
"""


class StateError(Exception):
    pass


class State:
    # Phase 26e — Genesis lockdown window. While the chain has zero
    # registered producers AND head_height < this value, only blocks
    # signed by the treasury address are accepted. Once the first
    # producer registers (treasury-signed REGISTER_PRODUCER tx) the
    # standard slot-election guard takes over; once `height` reaches the
    # lockdown ceiling the gate also opens unconditionally so a silent
    # treasury can't permanently freeze the chain.
    GENESIS_LOCKDOWN_HEIGHT_DEFAULT = 100

    def __init__(self, db_path: Path, treasury: str, dag_mode: bool = False,
                 genesis_lockdown_height: int = GENESIS_LOCKDOWN_HEIGHT_DEFAULT):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.treasury = treasury
        # Phase 24a: when True, accept multi-tip DAG and skip the strict
        # state_root match in apply_block (siblings legitimately diverge
        # until Phase 24b lands frontier-relative state).
        self.dag_mode = dag_mode
        # Phase 26e — int <= 0 disables the lockdown entirely (only
        # appropriate for single-node smoke tests where the operator
        # already runs the only block-producing key).
        self.genesis_lockdown_height = int(genesis_lockdown_height)
        # Phase 24b throughput — two-tier cache hierarchy that avoids
        # the genesis-replay penalty on `compute_frontier_state_root`:
        #
        # 1. _materialized_frontier — tracks the frozenset of frontier
        #    hashes that the persistent db's `accounts/contents/...`
        #    derived tables currently reflect. Updated by
        #    `_rebuild_materialized_state`. When a verify call asks for
        #    THIS frontier (the common linear-extension case), we can
        #    apply the block's extras inside a SAVEPOINT directly on
        #    the persistent state and roll back, skipping the tempfile
        #    replica entirely.
        # 2. _merge_cache — LRU map `frozenset(frontier_hashes) → state_root`
        #    for the no-extras path (e.g. helper queries that just want
        #    the canonical root for an arbitrary tip set). Hit ratio is
        #    near 1.0 once a frontier is computed once because state_roots
        #    are content-addressed and never need invalidation.
        self._materialized_frontier: frozenset | None = None
        self._materialized_root: bytes | None = None
        self._merge_cache_max = 256
        from collections import OrderedDict as _OD
        self._merge_cache: "OrderedDict[frozenset, bytes]" = _OD()
        with self._conn() as c:
            c.executescript(SCHEMA)
            # SQLite INTEGER is 8-byte signed (max ~9.2e18). 1e18 leaves
            # headroom for the EVM bridge (1 wei = 1 MORM at 1:1 scale).
            self._ensure_account(c, treasury, balance=10**18)  # 1e18 MORM

    def genesis_lockdown_active(self, height: int) -> bool:
        """Phase 26e — True when block production is locked to treasury.

        Logic: window applies only while no producers are registered. The
        first treasury-signed REGISTER_PRODUCER tx populates the table,
        slot election kicks in, and this returns False forever after.
        Height ceiling is the escape hatch — even with empty producers,
        once we pass it the chain reverts to "anyone may produce" so an
        offline treasury can't deadlock genesis.
        """
        if self.genesis_lockdown_height <= 0:
            return False
        if height >= self.genesis_lockdown_height:
            return False
        return len(self.list_producers()) == 0

    def _conn(self):
        c = sqlite3.connect(self.db_path, isolation_level=None)
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("PRAGMA foreign_keys=ON")
        return c

    @staticmethod
    def _ensure_account(c, addr: str, balance: int = 0):
        c.execute(
            "INSERT INTO accounts (address, balance) VALUES (?, ?) "
            "ON CONFLICT(address) DO NOTHING",
            (addr, balance),
        )

    # ---- block-level apply --------------------------------------------------

    def apply_block(self, block) -> bytes:
        """Validate & apply every tx, store the block, return new state_root.

        Phase 24b dispatch:
        - dag_mode=False (Phase 17 single-chain): apply txs directly to the
          materialized state and assert state_root matches block header.
        - dag_mode=True  (Phase 24b frontier-relative): verify the producer's
          claim by replaying the canonical merge of `block.parent_hashes`
          plus `block.transactions` strictly on top, then persist the block
          and rebuild the materialized state from the new canonical frontier.
        """
        # Phase 26e — Genesis lockdown gate. Applied BEFORE any tx work so
        # an attacker's block burns nothing on this node. This catches
        # both self-produced (locked treasury holder runs node, OK) and
        # imported (peer flooded the network, REJECTED) cases since both
        # paths funnel through apply_block.
        if self.genesis_lockdown_active(block.header.height):
            block_addr = crypto.address(block.header.producer)
            if block_addr != self.treasury:
                raise StateError(
                    f"26e genesis lockdown: only treasury "
                    f"({self.treasury[:10]}…) may produce until height "
                    f"{self.genesis_lockdown_height} or first REGISTER_PRODUCER; "
                    f"block is from {block_addr[:10]}…"
                )

        if self.dag_mode:
            return self._apply_block_dag(block)

        c = self._conn()
        c.execute("BEGIN IMMEDIATE")
        try:
            applied = []
            for tx in block.transactions:
                self._apply_tx(c, tx, block_ts=block.header.timestamp)
                applied.append(tx)
            root = self._compute_state_root(c)
            if root != block.header.state_root:
                raise StateError(
                    f"state_root mismatch: got {block.header.state_root.hex()}, computed {root.hex()}"
                )
            c.execute(
                "INSERT INTO blocks (hash, height, parents, producer, state_root, payload) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (block.hash().hex(), block.header.height,
                 json.dumps([h.hex() for h in block.header.parent_hashes]),
                 block.header.producer.hex(), root.hex(),
                 json.dumps(block.to_dict())),
            )
            c.execute("COMMIT")
            return root
        except Exception:
            c.execute("ROLLBACK")
            raise
        finally:
            c.close()

    def _apply_block_dag(self, block) -> bytes:
        """Phase 24b strict frontier-relative apply + Phase 24d rate limit.

        1. Phase 24d: reject if producer is over their R-blocks-per-10s cap.
        2. Phase 24b: compute expected_root via canonical replay of
           `block.parent_hashes` + strict apply of `block.transactions` on
           top (no skip).
        3. If expected_root != block.header.state_root → reject.
        4. Persist block in `blocks` table.
        5. Rebuild materialized derived state from the new canonical frontier
           (= all current tip hashes including the just-stored block).
        """
        # Phase 24d: per-producer rate limit. Cheap pre-check before the
        # expensive canonical replay below.
        if not self.producer_rate_limit_ok(block):
            R = self._producer_weight(crypto.address(block.header.producer))
            raise StateError(
                f"24d rate limit: producer "
                f"{crypto.address(block.header.producer)[:10]}… already has "
                f"≥{R} block(s) in last {self.PRODUCER_RATE_WINDOW_MS}ms"
            )

        # Step 2+3: Phase 24b verify against an isolated replay
        expected_root = self.compute_frontier_state_root(
            block.header.parent_hashes,
            extra_txs=block.transactions,
            extra_block_ts=block.header.timestamp,
            strict_extras=True,
        )
        if expected_root != block.header.state_root:
            raise StateError(
                f"24b state_root mismatch: producer claims "
                f"{block.header.state_root.hex()[:16]}… but canonical replay "
                f"yields {expected_root.hex()[:16]}…"
            )

        # Step 3+4: persist + rebuild materialized state
        c = self._conn()
        c.execute("BEGIN IMMEDIATE")
        try:
            c.execute(
                "INSERT INTO blocks (hash, height, parents, producer, state_root, payload) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (block.hash().hex(), block.header.height,
                 json.dumps([h.hex() for h in block.header.parent_hashes]),
                 block.header.producer.hex(), block.header.state_root.hex(),
                 json.dumps(block.to_dict())),
            )
            new_tips = self._tip_hashes_with_conn(c)
            # Phase 24b incremental rebuild — for the linear / multi-tip
            # absorbing case, skip wipe + canonical replay and apply the
            # block's txs directly on the materialized state (which is
            # already canonical(old_frontier)). Falls through to the
            # full rebuild for sibling / true-DAG-merge cases that need
            # canonical reordering.
            #
            # `MORM_FORCE_FULL_REBUILD=1` env disables the fast path so
            # operators / regression tests can compare the two state_roots
            # bit-for-bit. Helpful when validating the incremental path.
            _force_full = os.environ.get("MORM_FORCE_FULL_REBUILD") == "1"
            if (not _force_full) and self._can_incremental_apply(block, new_tips):
                self._apply_block_incremental(c, block)
            else:
                self._rebuild_materialized_state(c, new_tips)
            root = self._compute_state_root(c)
            c.execute("COMMIT")
            # Phase 24b — markers updated AFTER commit so the SAVEPOINT
            # shortcut on a future verify reads a frontier we know is
            # persisted. Also seed the merge_cache so no-extras lookups
            # for this frontier are O(1) immediately.
            new_frontier = frozenset(new_tips)
            self._materialized_frontier = new_frontier
            self._materialized_root = root
            self._merge_cache_put(new_frontier, root)
            return root
        except Exception:
            c.execute("ROLLBACK")
            raise
        finally:
            c.close()

    # ---- Phase 24b frontier-relative state ---------------------------------

    # Tables that are derived from txs and rebuilt on every canonical replay.
    # `blocks` is the source of truth for the DAG and is NOT wiped.
    _DERIVED_TABLES = (
        "accounts", "contents", "orders", "jobs", "worker_stats",
        "views", "bridge_mints", "bridge_burns", "account_tokens",
        "ai_services", "producers",
        # Phase 26a treasury multi-sig — both rebuilt from REGISTER_TREASURY_SIGNERS txs.
        "treasury_signers", "treasury_config",
    )

    # Phase 26a: treasury-only kinds. Once multi-sig is active, any of
    # these submitted as a top-level tx with sender=treasury is rejected
    # — they must be wrapped in MULTISIG_TX. Pre-multisig, behaviour is
    # unchanged (single-key treasury still works).
    _TREASURY_ONLY_KINDS = frozenset({
        TxKind.BRIDGE_MINT,
        TxKind.REGISTER_AI_SERVICE,
        TxKind.REGISTER_PRODUCER,
        TxKind.FINALIZE,
    })

    def _load_block_by_hash(self, hash_hex: str, c=None):
        """Load a Block from the blocks table. Returns None if not present
        (e.g. the genesis sentinel hash, or a block we haven't seen yet)."""
        owned = c is None
        if owned:
            c = self._conn()
        try:
            row = c.execute(
                "SELECT payload FROM blocks WHERE hash=?", (hash_hex,)
            ).fetchone()
            if not row:
                return None
            from .block import Block
            return Block.from_dict(json.loads(row[0]))
        finally:
            if owned:
                c.close()

    def _collect_ancestors(self, frontier_hashes, c=None) -> dict:
        """BFS from `frontier_hashes` toward genesis. Returns {block_hash: Block}.
        The genesis sentinel (hash with no stored block) is silently skipped."""
        owned = c is None
        if owned:
            c = self._conn()
        try:
            visited: dict = {}
            queue = list(frontier_hashes)
            while queue:
                bh = queue.pop()
                if bh in visited:
                    continue
                block = self._load_block_by_hash(bh.hex(), c=c)
                if block is None:
                    # Genesis or unknown — treat as boundary, do not walk further.
                    continue
                visited[bh] = block
                for ph in block.header.parent_hashes:
                    if ph not in visited:
                        queue.append(ph)
            return visited
        finally:
            if owned:
                c.close()

    def _canonical_tx_order(self, frontier_hashes, c=None) -> list:
        """Phase 24b §4 canonical order, with same-sender nonce stability.

        For each tx reachable from `frontier_hashes`, pick the canonical
        block containing it = (lowest-height, then lowest-block-hash). Use
        that block's timestamp as the tx's apply_ts.

        Sort key (deterministic across nodes that see the same DAG):
          1. canonical_height          — older blocks first
          2. sender_pubkey             — group same-sender txs together
          3. tx.nonce                  — ★ same-sender txs in nonce order
          4. tx.hash()                 — final tiebreak between different senders

        Open question 1 in DAG-DESIGN.md §8 noted "lower-hash-wins" for
        same-nonce conflicts; that still holds (different txs from the
        same sender with the same nonce would conflict on the nonce check
        and the lower-hash one wins because (sender, nonce) ties resolve
        on tx.hash()). The (sender, nonce) layer was missing in the
        original spec text; without it, multiple sequential txs from one
        sender (treasury bootstrap, viewer reward bursts, etc.) get
        sorted by tx_hash and skip half the apply chain on nonce
        mismatch. Adding nonce ordering is a strict refinement — the
        ordering remains a deterministic function of the DAG.

        Returns list of (Transaction, block_ts) pairs.
        """
        visited = self._collect_ancestors(frontier_hashes, c=c)
        tx_origin: dict = {}
        for block_hash, block in visited.items():
            for tx in block.transactions:
                th = tx.hash()
                key = (block.header.height, block_hash)
                if th not in tx_origin:
                    tx_origin[th] = (block.header.height, block_hash,
                                     block.header.timestamp, tx)
                else:
                    existing = (tx_origin[th][0], tx_origin[th][1])
                    if key < existing:
                        tx_origin[th] = (block.header.height, block_hash,
                                         block.header.timestamp, tx)
        items = sorted(
            tx_origin.values(),
            key=lambda v: (v[0], v[3].sender, v[3].nonce, v[3].hash()),
        )
        return [(tx, block_ts) for _, _, block_ts, tx in items]

    def _tip_hashes_with_conn(self, c) -> list:
        """tip_hashes() variant that reuses an existing transaction's connection.
        Required because tip_hashes() opens its own connection and would
        deadlock against an outer BEGIN IMMEDIATE."""
        row = c.execute("SELECT MAX(height) FROM blocks").fetchone()
        if not row or row[0] is None:
            from . import GENESIS_HASH
            return [GENESIS_HASH]
        tips = c.execute(
            "SELECT hash FROM blocks WHERE height = ?", (row[0],)
        ).fetchall()
        return [bytes.fromhex(t[0]) for t in tips]

    @classmethod
    def _build_replica(cls, treasury_addr: str):
        """Spin up a fresh, single-use State backed by a tempfile so canonical
        replay doesn't pollute the persistent db. Caller must `_destroy_replica`."""
        tmp = tempfile.NamedTemporaryFile(
            prefix="morm-replay-", suffix=".db", delete=False)
        tmp.close()
        replica = cls(Path(tmp.name), treasury=treasury_addr, dag_mode=False)
        replica._tmp_path = tmp.name
        return replica

    def _destroy_replica(self):
        path = getattr(self, "_tmp_path", None)
        if not path:
            return
        for p in (path, path + "-wal", path + "-shm", path + "-journal"):
            try:
                os.unlink(p)
            except FileNotFoundError:
                pass
        self._tmp_path = None

    # ---- Phase 24b throughput cache helpers --------------------------------

    def _merge_cache_get(self, key: frozenset) -> bytes | None:
        v = self._merge_cache.get(key)
        if v is not None:
            self._merge_cache.move_to_end(key)
        return v

    def _merge_cache_put(self, key: frozenset, value: bytes) -> None:
        self._merge_cache[key] = value
        self._merge_cache.move_to_end(key)
        while len(self._merge_cache) > self._merge_cache_max:
            self._merge_cache.popitem(last=False)

    def _try_savepoint_shortcut(
        self, frontier_hashes, extra_txs, extra_block_ts, strict_extras,
    ) -> bytes | None:
        """Phase 24b fast path for the common "block extends current
        materialized frontier" case. If the persistent db already holds
        the canonical state for `frontier_hashes`, we can apply the
        block's extras inside a SAVEPOINT, read state_root, and roll
        back — skipping the tempfile replica + genesis replay (O(N)).

        Returns the computed state_root, or None if the shortcut isn't
        applicable (frontier mismatch, or no materialized state cached).
        """
        if self._materialized_frontier is None:
            return None
        if frozenset(frontier_hashes) != self._materialized_frontier:
            return None
        # Frontier matches — open a SAVEPOINT on the persistent db, apply
        # extras, read root, roll back. The persistent db is unchanged.
        c = self._conn()
        c.execute("BEGIN IMMEDIATE")
        try:
            if extra_txs:
                for tx in extra_txs:
                    try:
                        self._apply_tx(c, tx, block_ts=extra_block_ts)
                    except StateError:
                        if strict_extras:
                            raise
                        continue
            root = self._compute_state_root(c)
            return root
        finally:
            # ROLLBACK regardless: we never want this transaction to commit;
            # the persistent state must remain at the materialized frontier
            # until apply_block decides to actually persist the new block.
            try: c.execute("ROLLBACK")
            except Exception: pass
            c.close()

    def compute_frontier_state_root(
        self, frontier_hashes,
        extra_txs=None, extra_block_ts: int | None = None,
        strict_extras: bool = False,
    ) -> bytes:
        """Phase 24b state_root for an arbitrary frontier.

        Replays the canonical tx order on a fresh in-memory replica from
        genesis; optionally applies `extra_txs` on top (used by producer
        to compute its own block's state_root, and by importer to verify
        a peer's block).

        - `strict_extras=True` raises on any extra tx that fails (used in
          apply_block verification: the producer's own block must apply
          cleanly on top of its parents' canonical state).
        - `strict_extras=False` skips failing extras (used by producer's
          own filter pass).

        Phase 24b throughput optimizations (in priority order):
        1. SAVEPOINT shortcut when frontier == materialized — O(extras)
           instead of O(ancestors). Covers the linear-extension case
           that dominates production.
        2. _merge_cache for the no-extras path — O(1) for repeat
           queries on the same frontier.
        3. Otherwise: existing tempfile replica + canonical replay.
        """
        # 1. SAVEPOINT shortcut (works for both extras / no-extras cases).
        shortcut = self._try_savepoint_shortcut(
            frontier_hashes, extra_txs, extra_block_ts, strict_extras)
        if shortcut is not None:
            return shortcut

        # 2. No-extras lookup in merge_cache.
        cache_key = frozenset(frontier_hashes) if not extra_txs else None
        if cache_key is not None:
            cached = self._merge_cache_get(cache_key)
            if cached is not None:
                return cached

        # 3. Slow path — full genesis replay on a tempfile replica.
        replica = self._build_replica(self.treasury)
        try:
            c = replica._conn()
            c.execute("BEGIN IMMEDIATE")
            try:
                # 1. Canonical replay (skip-on-conflict — sibling races OK)
                for tx, ts in self._canonical_tx_order(frontier_hashes):
                    try:
                        replica._apply_tx(c, tx, block_ts=ts)
                    except StateError:
                        continue
                # 2. Apply extras
                if extra_txs:
                    for tx in extra_txs:
                        try:
                            replica._apply_tx(c, tx, block_ts=extra_block_ts)
                        except StateError:
                            if strict_extras:
                                raise
                            continue
                root = replica._compute_state_root(c)
                c.execute("COMMIT")
                if cache_key is not None:
                    self._merge_cache_put(cache_key, root)
                return root
            except Exception:
                c.execute("ROLLBACK")
                raise
            finally:
                c.close()
        finally:
            replica._destroy_replica()

    def replay_with_filter(
        self, parent_hashes, candidate_txs, block_ts: int,
    ):
        """Producer-side helper: returns (applied_txs, state_root).

        Builds canonical(parent_hashes), then tries each candidate tx in
        order. Successful txs are kept; failures are dropped (e.g. nonce
        conflict because a sibling already consumed the slot). The
        returned state_root is what the producer should sign into the
        block header — it matches what every importer will compute via
        compute_frontier_state_root(parent_hashes, extras=applied).

        Phase 24b throughput — same SAVEPOINT shortcut as
        compute_frontier_state_root. When the producer's parents match
        the current materialized frontier (the linear-extension case),
        we apply candidates directly on the persistent db inside a
        transaction and ROLLBACK after capturing the result. This kills
        the genesis-replay penalty for every block produced.
        """
        # Phase 24b shortcut — if parent_hashes == materialized frontier.
        if (self._materialized_frontier is not None
                and frozenset(parent_hashes) == self._materialized_frontier):
            c = self._conn()
            c.execute("BEGIN IMMEDIATE")
            try:
                applied = []
                for tx in candidate_txs:
                    try:
                        self._apply_tx(c, tx, block_ts=block_ts)
                        applied.append(tx)
                    except StateError as e:
                        sys.stderr.write(
                            f"[24b producer] tx skipped vs canonical state: "
                            f"{type(e).__name__}: {e}\n"
                        )
                        continue
                root = self._compute_state_root(c)
                return applied, root
            finally:
                try: c.execute("ROLLBACK")
                except Exception: pass
                c.close()

        # Slow path — replica + genesis replay (DAG sibling case).
        replica = self._build_replica(self.treasury)
        try:
            c = replica._conn()
            c.execute("BEGIN IMMEDIATE")
            try:
                for tx, ts in self._canonical_tx_order(parent_hashes):
                    try:
                        replica._apply_tx(c, tx, block_ts=ts)
                    except StateError:
                        continue
                applied = []
                for tx in candidate_txs:
                    try:
                        replica._apply_tx(c, tx, block_ts=block_ts)
                        applied.append(tx)
                    except StateError as e:
                        sys.stderr.write(
                            f"[24b producer] tx skipped vs canonical state: "
                            f"{type(e).__name__}: {e}\n"
                        )
                        continue
                root = replica._compute_state_root(c)
                c.execute("COMMIT")
                return applied, root
            except Exception:
                c.execute("ROLLBACK")
                raise
            finally:
                c.close()
        finally:
            replica._destroy_replica()

    def _can_incremental_apply(self, block, new_tips) -> bool:
        """Phase 24b incremental rebuild — return True iff the open
        transaction's persistent state can be advanced to canonical
        `new_tips` by simply applying `block.transactions` on top, with
        no wipe + replay.

        Conditions (all must hold):
        1. We have a known `_materialized_frontier` (post-init invariant).
        2. `block.parent_hashes ⊆ old_materialized_frontier` — the block
           extends a tip we already absorbed; we don't need to backfill
           anything.
        3. `new_tips == (old_materialized_frontier - block.parents) ∪
           {block.hash()}` — no other new sibling appeared. This is the
           "linear / multi-tip absorbing" case.

        Sibling cases (block.parents ⊄ old_frontier, or new_tips
        introduces a NEW non-block tip) bail out to the safe slow path
        because canonical_tx_order may interleave their txs with the
        materialized state's, breaking the "extras go last" invariant.
        """
        if self._materialized_frontier is None:
            return False
        parent_set = set(block.header.parent_hashes)
        if not parent_set.issubset(self._materialized_frontier):
            return False
        expected = (self._materialized_frontier - parent_set) | {block.hash()}
        return frozenset(new_tips) == expected

    def _apply_block_incremental(self, c, block) -> None:
        """Apply `block.transactions` on the open transaction `c` directly,
        skipping wipe + canonical replay. Caller has already verified via
        `_can_incremental_apply` that this is safe.

        Same skip-on-StateError semantics as _rebuild_materialized_state's
        merge layer: sibling races may legitimately reject some txs."""
        for tx in block.transactions:
            try:
                self._apply_tx(c, tx, block_ts=block.header.timestamp)
            except StateError as e:
                sys.stderr.write(
                    f"[24b incremental] tx skipped: "
                    f"{type(e).__name__}: {e}\n"
                )
                continue

    def _rebuild_materialized_state(self, c, frontier_hashes):
        """Wipe derived tables and re-apply canonical txs in the open
        transaction `c`. Called by `_apply_block_dag` after persisting a
        new block, so that every node's queryable state matches the
        canonical merged frontier.

        Phase 24b throughput — the caller commits the surrounding tx,
        and only then should set `_materialized_frontier` / `_materialized_root`
        (see `_apply_block_dag`). Setting them here would expose a window
        where the markers point at a frontier whose state hasn't been
        persisted yet; a concurrent reader on a different connection
        would then see the OLD persistent state behind a NEW marker.
        """
        for table in self._DERIVED_TABLES:
            c.execute(f"DELETE FROM {table}")
        # Re-seed treasury (matches __init__ supply).
        self._ensure_account(c, self.treasury, balance=10**18)
        for tx, ts in self._canonical_tx_order(frontier_hashes, c=c):
            try:
                self._apply_tx(c, tx, block_ts=ts)
            except StateError as e:
                # This is the merge layer — sibling conflicts are expected.
                sys.stderr.write(
                    f"[24b merge] canonical replay skipped tx: "
                    f"{type(e).__name__}: {e}\n"
                )
                continue

    def frontier_root(self, frontier_hashes=None) -> bytes:
        """Hash of the sorted current tip set — an O(tips) cheap identifier
        that lets two nodes quickly tell whether they're on the same DAG
        frontier without comparing full state. Spec §6 Wire format."""
        if frontier_hashes is None:
            frontier_hashes = self.tip_hashes()
        h = hashlib.sha256()
        for fh in sorted(frontier_hashes):
            h.update(fh)
        return h.digest()

    # ---- Phase 24c common-ancestor finality --------------------------------

    def _all_ancestors(self, block_hash: bytes, c=None) -> set:
        """All transitive ancestor hashes of `block_hash` (NOT including the
        block itself). Stops at the genesis sentinel (no stored block)."""
        owned = c is None
        if owned:
            c = self._conn()
        try:
            visited: set = set()
            queue = [block_hash]
            while queue:
                bh = queue.pop()
                block = self._load_block_by_hash(bh.hex(), c=c)
                if block is None:
                    continue
                for ph in block.header.parent_hashes:
                    if ph not in visited:
                        visited.add(ph)
                        queue.append(ph)
            return visited
        finally:
            if owned:
                c.close()

    def common_ancestors(self, tip_hashes, c=None) -> set:
        """Block hashes that are ancestors of ALL given tips (intersection).

        For Phase 24c finality (`finalized_blocks`): a block is provably
        finalized iff every honest tip already builds on top of it. The
        deepest such block is the finalized head. Returns empty set if
        `tip_hashes` is empty."""
        if not tip_hashes:
            return set()
        owned = c is None
        if owned:
            c = self._conn()
        try:
            common = self._all_ancestors(tip_hashes[0], c=c)
            for tip in tip_hashes[1:]:
                if not common:
                    break
                common &= self._all_ancestors(tip, c=c)
            return common
        finally:
            if owned:
                c.close()

    # ---- Phase 24d per-producer rate limit -------------------------------

    # Window in milliseconds over which a producer's recent seal count is
    # measured. The cap is R blocks per window where R = producer weight.
    # Env override (`MORM_PRODUCER_RATE_WINDOW_MS`) is intended for
    # throughput benchmarks and stress tests where the 10s production
    # quota would otherwise dominate the measurement.
    PRODUCER_RATE_WINDOW_MS = int(os.environ.get(
        "MORM_PRODUCER_RATE_WINDOW_MS", "10000"))

    def _producer_weight(self, producer_address: str, c=None) -> int:
        """Phase 17a/PoUW weight = 1 + worker_stats.completed. Used by both
        slot election (Phase 17a) and the 24d rate limit cap."""
        owned = c is None
        if owned:
            c = self._conn()
        try:
            row = c.execute(
                "SELECT completed FROM worker_stats WHERE address = ?",
                (producer_address,),
            ).fetchone()
            return 1 + int(row[0] if row else 0)
        finally:
            if owned:
                c.close()

    def _producer_seal_count_in_window(
        self, producer_pubkey_hex: str,
        window_ms: int = PRODUCER_RATE_WINDOW_MS,
        c=None,
    ) -> int:
        """Count blocks sealed by this producer whose `header.timestamp` is
        within the last `window_ms` milliseconds of wall clock. Walks the
        most recent 100 blocks for this producer (sufficient for any sane
        rate cap; well above the realistic upper bound of weight)."""
        import time
        now_ms = int(time.time() * 1000)
        cutoff = now_ms - window_ms
        owned = c is None
        if owned:
            c = self._conn()
        try:
            rows = c.execute(
                "SELECT payload FROM blocks WHERE producer = ? "
                "ORDER BY height DESC LIMIT 100",
                (producer_pubkey_hex,),
            ).fetchall()
            n = 0
            for (payload_json,) in rows:
                ts = json.loads(payload_json)["header"]["timestamp"]
                if ts >= cutoff:
                    n += 1
            return n
        finally:
            if owned:
                c.close()

    def producer_rate_limit_ok(self, block, c=None) -> bool:
        """Phase 24d: True iff accepting `block` would NOT push its producer
        past the R-blocks-per-10s cap (R = producer weight).

        - R = 1 + worker_stats.completed  (PoUW reward → higher rate cap).
        - Window: last 10 s of wall-clock time, inclusive of `block`.
        - Rationale: with slot election removed in 24a, a malicious producer
          could otherwise spam siblings indefinitely. Soft rate limit
          preserves the §1 tokenomics (PoUW workers earn higher seal rate)
          without resurrecting Phase 17a's hard slot monopoly.
        - Old blocks (catch-up sync) automatically pass — their timestamps
          fall outside the recent window."""
        producer_hex = block.header.producer.hex()
        producer_addr = crypto.address(block.header.producer)
        # Counting on persistent state (not including the new block yet).
        # Accepting the block would make the count `current + 1`, so reject
        # when current ≥ R.
        R = self._producer_weight(producer_addr, c=c)
        n = self._producer_seal_count_in_window(producer_hex, c=c)
        return n < R

    def producer_rate_window(self, c=None) -> dict:
        """For `/info` introspection: each registered producer's current
        seal count in the rate window, plus their cap R. Lets operators see
        who's near the cap and explains rejected-block events."""
        owned = c is None
        if owned:
            c = self._conn()
        try:
            producers = c.execute(
                "SELECT pubkey, address, name FROM producers"
            ).fetchall()
            out = []
            for pk, addr, name in producers:
                R = self._producer_weight(addr, c=c)
                n = self._producer_seal_count_in_window(pk, c=c)
                out.append({
                    "pubkey": pk, "address": addr, "name": name,
                    "weight_R": R, "recent_seals": n,
                    "window_ms": self.PRODUCER_RATE_WINDOW_MS,
                })
            return {"window_ms": self.PRODUCER_RATE_WINDOW_MS,
                    "producers": out}
        finally:
            if owned:
                c.close()

    def finalized_height_dag(self, c=None) -> int:
        """Phase 24c: max height of any block that is a common ancestor of
        every current tip, *and* the tip count meets the witness threshold
        (≥⅔ of registered producers).

        - If fewer registered producers than 1: no DAG-mode finality (returns 0).
        - If fewer concurrent tips than threshold: insufficient witnesses, 0.
        - Else: walk each tip's ancestors, intersect, return max(height).

        Replaces the Phase 17 `head − FINALITY_DEPTH` rule for nodes running
        in `--dag-mode`. Single-chain nodes keep the old K-depth rule via the
        existing `/info` finalized computation."""
        owned = c is None
        if owned:
            c = self._conn()
        try:
            tips = self._tip_hashes_with_conn(c)
            if not tips:
                return 0
            # Witness threshold: ⌈2/3 · N⌉ where N = registered producers.
            row = c.execute("SELECT COUNT(*) FROM producers").fetchone()
            n_producers = int(row[0] or 0)
            if n_producers <= 0:
                return 0
            import math
            threshold = max(1, math.ceil(2 * n_producers / 3))
            if len(tips) < threshold:
                return 0
            common = self.common_ancestors(tips, c=c)
            if not common:
                return 0
            placeholders = ",".join("?" * len(common))
            row = c.execute(
                f"SELECT MAX(height) FROM blocks WHERE hash IN ({placeholders})",
                tuple(h.hex() for h in common),
            ).fetchone()
            return int(row[0] or 0)
        finally:
            if owned:
                c.close()

    # ---- transaction dispatch ----------------------------------------------

    def _apply_tx(self, c, tx: Transaction, block_ts: int | None = None):
        """Apply tx to the open transaction `c`. `block_ts` is the deterministic
        time used for any *_at columns; if omitted (producer pre-block path),
        the producer must supply one and re-call _apply_tx with it."""
        if not tx.verify():
            raise StateError("bad signature")

        sender_addr = crypto.address(tx.sender)
        self._ensure_account(c, sender_addr)
        row = c.execute("SELECT nonce, locked FROM accounts WHERE address=?",
                         (sender_addr,)).fetchone()
        nonce, locked = row[0], row[1]
        if locked:
            raise StateError(f"account {sender_addr} is locked")
        if tx.nonce != nonce:
            raise StateError(f"nonce mismatch: tx.nonce={tx.nonce} expected={nonce}")

        ts = block_ts if block_ts is not None else _ts()

        # Phase 26a: once treasury multi-sig is active, treasury-only
        # kinds cannot be submitted directly with a single-key signature
        # by the treasury account. They must be wrapped in MULTISIG_TX.
        # The MULTISIG_TX handler then unwraps and dispatches the inner
        # tx via `_apply_inner_treasury_tx` (which bypasses this guard
        # by passing `from_multisig=True`).
        if (tx.kind in self._TREASURY_ONLY_KINDS
                and sender_addr == self.treasury
                and self._is_treasury_multisig_active(c)):
            raise StateError(
                f"treasury multi-sig active: kind {tx.kind.name} "
                f"must be wrapped in MULTISIG_TX")

        if tx.kind == TxKind.REGISTER_CONTENT:
            self._tx_register_content(c, sender_addr, tx, ts)
        elif tx.kind == TxKind.CREATE_ORDER:
            self._tx_create_order(c, sender_addr, tx, ts)
        elif tx.kind == TxKind.SUBMIT_PROOF:
            self._tx_submit_proof(c, sender_addr, tx)
        elif tx.kind == TxKind.FINALIZE:
            self._tx_finalize(c, sender_addr, tx)
        elif tx.kind == TxKind.STAKE:
            self._tx_stake(c, sender_addr, tx)
        elif tx.kind == TxKind.TRANSFER:
            self._tx_transfer(c, sender_addr, tx)
        elif tx.kind == TxKind.VIEW_REWARD:
            self._tx_view_reward(c, sender_addr, tx, ts)
        elif tx.kind == TxKind.BRIDGE_MINT:
            self._tx_bridge_mint(c, sender_addr, tx, ts)
        elif tx.kind == TxKind.BRIDGE_BURN:
            self._tx_bridge_burn(c, sender_addr, tx, ts)
        elif tx.kind == TxKind.POST_JOB:
            self._tx_post_job(c, sender_addr, tx, ts)
        elif tx.kind == TxKind.CLAIM_JOB:
            self._tx_claim_job(c, sender_addr, tx)
        elif tx.kind == TxKind.SUBMIT_WORK_PROOF:
            self._tx_submit_work_proof(c, sender_addr, tx)
        elif tx.kind == TxKind.REGISTER_AI_SERVICE:
            self._tx_register_ai_service(c, sender_addr, tx, ts)
        elif tx.kind == TxKind.REGISTER_PRODUCER:
            self._tx_register_producer(c, sender_addr, tx, ts)
        elif tx.kind == TxKind.REGISTER_TREASURY_SIGNERS:
            self._tx_register_treasury_signers(c, sender_addr, tx, ts)
        elif tx.kind == TxKind.MULTISIG_TX:
            self._tx_multisig_tx(c, sender_addr, tx, ts)
        else:
            raise StateError(f"unknown tx kind {tx.kind}")

        c.execute("UPDATE accounts SET nonce = nonce + 1 WHERE address = ?",
                  (sender_addr,))

    # -- handlers -----------------------------------------------------------

    def _tx_register_content(self, c, sender: str, tx: Transaction, ts: int):
        p = tx.payload
        cid, rh, gid = p["content_id"], p["root_hash"], p.get("generation_id")
        if c.execute("SELECT 1 FROM contents WHERE content_id=?", (cid,)).fetchone():
            raise StateError("content already registered")
        if gid:
            if c.execute("SELECT 1 FROM contents WHERE generation_id=?", (gid,)).fetchone():
                raise StateError("generation_id collision")
            # Phase 14b: if any AI services are whitelisted, demand a valid
            # attestation from one of them.
            n_services = c.execute("SELECT COUNT(*) FROM ai_services").fetchone()[0]
            if n_services > 0:
                ai_pubkey = p.get("ai_pubkey")
                ai_signature = p.get("ai_signature")
                if not (ai_pubkey and ai_signature):
                    raise StateError("generation_id requires ai_pubkey + ai_signature")
                if not c.execute("SELECT 1 FROM ai_services WHERE pubkey=?",
                                 (ai_pubkey,)).fetchone():
                    raise StateError("ai_pubkey not whitelisted")
                from . import crypto as _crypto
                # signed message = generation_id_bytes || content_id_bytes
                msg = (bytes.fromhex(gid.removeprefix("0x"))
                       + bytes.fromhex(cid.removeprefix("0x")))
                pk = bytes.fromhex(ai_pubkey)
                sig = bytes.fromhex(ai_signature)
                if not _crypto.verify(pk, sig, msg):
                    raise StateError("invalid AI service signature")
        c.execute(
            "INSERT INTO contents (content_id, root_hash, generation_id, creator, registered_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (cid, rh, gid, sender, ts),
        )

    def _tx_register_producer(self, c, sender: str, tx: Transaction, ts: int):
        if sender != self.treasury:
            raise StateError("only treasury can register producers")
        from . import crypto as _crypto
        p = tx.payload
        pk = p["producer_pubkey"]
        if len(pk) != 64:
            raise StateError("producer_pubkey must be 64 hex chars (32 bytes)")
        if c.execute("SELECT 1 FROM producers WHERE pubkey=?", (pk,)).fetchone():
            raise StateError("producer already registered")
        addr = _crypto.address(bytes.fromhex(pk))
        c.execute(
            "INSERT INTO producers (pubkey, address, name, registered_at) "
            "VALUES (?, ?, ?, ?)",
            (pk, addr, p["name"], ts),
        )

    # ---- Phase 26a: Treasury multi-sig (M-of-N) ------------------------

    def _is_treasury_multisig_active(self, c) -> bool:
        """True iff treasury_config.enabled = 1. Used by `_apply_tx` to
        gate treasury-only kinds: pre-activation, single-key signs;
        post-activation, only MULTISIG_TX wrappers are accepted."""
        row = c.execute(
            "SELECT enabled FROM treasury_config WHERE rowid = 1"
        ).fetchone()
        return bool(row and row[0])

    def _list_treasury_signer_pubkeys(self, c) -> set:
        """Set of registered treasury signer pubkeys (hex)."""
        rows = c.execute("SELECT pubkey FROM treasury_signers").fetchall()
        return {r[0] for r in rows}

    def _tx_register_treasury_signers(self, c, sender: str,
                                       tx: Transaction, ts: int):
        """Phase 26a bootstrap. Must be signed by the original
        single-key treasury, exactly once. Replaces the previous
        single-key authority with a multi-sig signer set + threshold M."""
        if sender != self.treasury:
            raise StateError(
                "REGISTER_TREASURY_SIGNERS must be signed by the "
                "original single-key treasury")
        if self._is_treasury_multisig_active(c):
            raise StateError(
                "treasury multi-sig already active; rotate via "
                "MULTISIG_TX-wrapped REGISTER_TREASURY_SIGNERS instead")
        p = tx.payload
        signers = p.get("signers") or []
        threshold = int(p.get("threshold", 0))
        if not isinstance(signers, list) or not signers:
            raise StateError("signers must be a non-empty list")
        n = len(signers)
        if threshold < 1 or threshold > n:
            raise StateError(
                f"threshold must be in [1, {n}], got {threshold}")
        seen = set()
        for s in signers:
            pk = s.get("pubkey")
            name = s.get("name") or ""
            if not pk or len(pk) != 64:
                raise StateError(f"signer pubkey must be 64 hex chars: {pk!r}")
            if pk in seen:
                raise StateError(f"duplicate signer pubkey: {pk}")
            seen.add(pk)
            c.execute(
                "INSERT INTO treasury_signers (pubkey, name, registered_at) "
                "VALUES (?, ?, ?)",
                (pk, name, ts),
            )
        c.execute(
            "INSERT INTO treasury_config (rowid, threshold, n_signers, enabled, enabled_at) "
            "VALUES (1, ?, ?, 1, ?)",
            (threshold, n, ts),
        )

    def _tx_multisig_tx(self, c, sender: str, tx: Transaction, ts: int):
        """Phase 26a: validate the wrapper, then apply the inner tx as
        if it had been signed by the (logical) treasury account.

        Wire validation:
          1. multi-sig must be active (otherwise nobody set up signers
             and the wrapper is meaningless).
          2. submitter (`sender`) must be a registered signer.
          3. inner_kind must be one of `_TREASURY_ONLY_KINDS`.
          4. payload.treasury_nonce must equal the treasury account's
             current nonce (anti-replay binder; cosigners committed to
             this specific execution slot).
          5. >= threshold signatures, all from distinct registered
             signer pubkeys, each verifying against
             multisig_signing_bytes(inner_kind, inner_payload,
             treasury, treasury_nonce).

        Inner application: dispatches to the existing _tx_* handler with
        sender forced to the treasury address. The inner tx is *not*
        re-signed — its authority comes from the M cosignatures."""
        if not self._is_treasury_multisig_active(c):
            raise StateError(
                "MULTISIG_TX requires treasury_config.enabled=1; "
                "bootstrap with REGISTER_TREASURY_SIGNERS first")
        signer_set = self._list_treasury_signer_pubkeys(c)
        if tx.sender.hex() not in signer_set:
            raise StateError(
                f"submitter {tx.sender.hex()[:16]}… is not a registered "
                f"treasury signer")
        cfg = c.execute(
            "SELECT threshold FROM treasury_config WHERE rowid = 1"
        ).fetchone()
        threshold = int(cfg[0])

        p = tx.payload
        inner_kind = TxKind(int(p["inner_kind"]))
        inner_payload = p["inner_payload"]
        expected_nonce = int(p["treasury_nonce"])
        sigs = p.get("signatures") or []
        if inner_kind not in self._TREASURY_ONLY_KINDS:
            raise StateError(
                f"MULTISIG_TX inner_kind {inner_kind.name} is not a "
                f"treasury-only kind")
        treasury_nonce_row = c.execute(
            "SELECT nonce FROM accounts WHERE address = ?",
            (self.treasury,),
        ).fetchone()
        treasury_nonce = int(treasury_nonce_row[0]) if treasury_nonce_row else 0
        if expected_nonce != treasury_nonce:
            raise StateError(
                f"treasury_nonce mismatch: payload says {expected_nonce}, "
                f"chain has {treasury_nonce}")

        msg = Transaction.multisig_signing_bytes(
            int(inner_kind), inner_payload, self.treasury, treasury_nonce)

        seen_pubkeys: set = set()
        valid_count = 0
        for s in sigs:
            pk_hex = s.get("pubkey")
            sig_hex = s.get("sig")
            if not pk_hex or not sig_hex:
                raise StateError("each signature needs pubkey + sig hex")
            if pk_hex in seen_pubkeys:
                raise StateError(f"duplicate cosigner pubkey: {pk_hex[:16]}…")
            if pk_hex not in signer_set:
                raise StateError(
                    f"cosigner {pk_hex[:16]}… not in treasury signer set")
            seen_pubkeys.add(pk_hex)
            try:
                pk_bytes = bytes.fromhex(pk_hex)
                sig_bytes = bytes.fromhex(sig_hex)
            except ValueError:
                raise StateError("cosigner hex decode failed")
            if not crypto.verify(pk_bytes, sig_bytes, msg):
                raise StateError(
                    f"cosigner signature invalid for {pk_hex[:16]}…")
            valid_count += 1
        if valid_count < threshold:
            raise StateError(
                f"insufficient cosignatures: got {valid_count}, need {threshold}")

        # Synthesize an inner Transaction whose sender = treasury and
        # nonce = treasury_nonce; then dispatch to the matching handler.
        # We never actually verify() the inner sig (it has none — its
        # authority is the M cosignatures we just checked).
        treasury_pub_bytes = self._treasury_address_to_pub(c)
        inner_tx = Transaction(
            kind=inner_kind,
            sender=treasury_pub_bytes,
            nonce=treasury_nonce,
            payload=inner_payload,
            signature=b"",
        )
        # Bump the treasury nonce ourselves (we bypass _apply_tx so we
        # have to emulate the post-handler nonce++ that _apply_tx does).
        if inner_kind == TxKind.BRIDGE_MINT:
            self._tx_bridge_mint(c, self.treasury, inner_tx, ts)
        elif inner_kind == TxKind.REGISTER_AI_SERVICE:
            self._tx_register_ai_service(c, self.treasury, inner_tx, ts)
        elif inner_kind == TxKind.REGISTER_PRODUCER:
            self._tx_register_producer(c, self.treasury, inner_tx, ts)
        elif inner_kind == TxKind.FINALIZE:
            self._tx_finalize(c, self.treasury, inner_tx)
        else:
            raise StateError(f"unhandled inner_kind: {inner_kind.name}")
        c.execute(
            "UPDATE accounts SET nonce = nonce + 1 WHERE address = ?",
            (self.treasury,),
        )

    def _treasury_address_to_pub(self, c) -> bytes:
        """Return a placeholder bytes32 used as the inner tx's `sender`
        field. The address-derivation map is one-way, so we can't
        recover the pubkey from the m0r address alone — but the inner
        tx's `sender` is only used for `crypto.address(sender) ==
        self.treasury` checks downstream, which we already passed by
        passing self.treasury directly to the handler. Returning all
        zeros marks this as "synthesized; do not use for sig verify"."""
        return b"\x00" * 32

    def _tx_register_ai_service(self, c, sender: str, tx: Transaction, ts: int):
        if sender != self.treasury:
            raise StateError("only treasury can register AI services")
        p = tx.payload
        pk = p["ai_pubkey"]
        if len(pk) != 64:
            raise StateError("ai_pubkey must be 64 hex chars (32 bytes)")
        if c.execute("SELECT 1 FROM ai_services WHERE pubkey=?", (pk,)).fetchone():
            raise StateError("ai_pubkey already registered")
        c.execute(
            "INSERT INTO ai_services (pubkey, name, registered_at) VALUES (?, ?, ?)",
            (pk, p["name"], ts),
        )

    def _tx_create_order(self, c, sender: str, tx: Transaction, ts: int):
        p = tx.payload
        oid, cid, seller, value = p["order_id"], p["content_id"], p["seller"], int(p["value"])
        if c.execute("SELECT 1 FROM orders WHERE order_id=?", (oid,)).fetchone():
            raise StateError("order exists")
        if not c.execute("SELECT 1 FROM contents WHERE content_id=?", (cid,)).fetchone():
            raise StateError("unknown content")
        bal = c.execute("SELECT balance FROM accounts WHERE address=?",
                        (sender,)).fetchone()[0]
        if bal < value:
            raise StateError("insufficient balance")
        # check seller not locked
        row = c.execute("SELECT locked FROM accounts WHERE address=?", (seller,)).fetchone()
        if row and row[0]:
            raise StateError("seller is locked")
        self._ensure_account(c, seller)

        fee = (value * FEE_BPS) // BPS_DENOM
        amt = value - fee
        c.execute("UPDATE accounts SET balance=balance-? WHERE address=?", (value, sender))
        c.execute("UPDATE accounts SET balance=balance+? WHERE address=?", (fee, self.treasury))
        # the contract address holds escrow funds; we model this as a synthetic account "escrow"
        self._ensure_account(c, ESCROW_ACCOUNT)
        c.execute("UPDATE accounts SET balance=balance+? WHERE address=?", (amt, ESCROW_ACCOUNT))
        c.execute(
            "INSERT INTO orders (order_id, content_id, buyer, seller, amount, fee, status, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, 1, ?)",
            (oid, cid, sender, seller, amt, fee, ts),
        )

    def _tx_submit_proof(self, c, sender: str, tx: Transaction):
        p = tx.payload
        oid, role, ph = p["order_id"], p["role"], p["proof_hash"]
        row = c.execute(
            "SELECT buyer, seller, status FROM orders WHERE order_id=?", (oid,)
        ).fetchone()
        if not row:
            raise StateError("unknown order")
        buyer, seller, status = row
        if role == "packing":
            if sender != seller:
                raise StateError("only seller submits packing")
            if status != 1:
                raise StateError("packing requires status=Created")
            c.execute(
                "UPDATE orders SET packing_hash=?, status=2 WHERE order_id=?",
                (ph, oid),
            )
        elif role == "opening":
            if sender != buyer:
                raise StateError("only buyer submits opening")
            if status != 2:
                raise StateError("opening requires status=PackingDone")
            c.execute(
                "UPDATE orders SET opening_hash=?, status=3 WHERE order_id=?",
                (ph, oid),
            )
        else:
            raise StateError(f"unknown role {role!r}")

    def _tx_finalize(self, c, sender: str, tx: Transaction):
        p = tx.payload
        if sender != self.treasury:
            raise StateError("only treasury finalizes")
        oid, valid = p["order_id"], bool(p["valid"])
        row = c.execute(
            "SELECT seller, buyer, amount, status FROM orders WHERE order_id=?", (oid,)
        ).fetchone()
        if not row:
            raise StateError("unknown order")
        seller, buyer, amount, status = row
        if status != 3:
            raise StateError("finalize requires status=OpeningDone")
        if valid:
            c.execute("UPDATE accounts SET balance=balance-? WHERE address=?",
                      (amount, ESCROW_ACCOUNT))
            c.execute("UPDATE accounts SET balance=balance+? WHERE address=?",
                      (amount, seller))
            c.execute("UPDATE orders SET status=4 WHERE order_id=?", (oid,))
        else:
            c.execute("UPDATE accounts SET balance=balance-? WHERE address=?",
                      (amount, ESCROW_ACCOUNT))
            c.execute("UPDATE accounts SET balance=balance+? WHERE address=?",
                      (amount, buyer))
            # slash + lock the seller
            stake = c.execute("SELECT stake FROM accounts WHERE address=?",
                              (seller,)).fetchone()[0]
            c.execute(
                "UPDATE accounts SET stake=0, locked=1 WHERE address=?", (seller,)
            )
            if stake > 0:
                c.execute(
                    "UPDATE accounts SET balance=balance+? WHERE address=?",
                    (stake, self.treasury),
                )
            c.execute("UPDATE orders SET status=5 WHERE order_id=?", (oid,))

    def _tx_stake(self, c, sender: str, tx: Transaction):
        amount = int(tx.payload["amount"])
        bal = c.execute("SELECT balance FROM accounts WHERE address=?",
                        (sender,)).fetchone()[0]
        if bal < amount:
            raise StateError("insufficient balance for stake")
        c.execute("UPDATE accounts SET balance=balance-?, stake=stake+? WHERE address=?",
                  (amount, amount, sender))

    def _tx_bridge_mint(self, c, sender: str, tx: Transaction, ts: int):
        """Treasury-only: relayer asserts an EVM Locked event was observed.
        For native MORM (token='MORM' or absent) this draws from treasury.balance.
        For ERC-20 (token='USDC', token_address=0x...) it credits a separate
        account_tokens row, no treasury draw — the L1 simply mirrors the EVM lock."""
        if sender != self.treasury:
            raise StateError("only treasury can BRIDGE_MINT")
        p = tx.payload
        evm_id = p["evm_lock_id"]
        recipient = p["to"]
        amount = int(p["amount"])
        token = p.get("token", "MORM")
        token_address = p.get("token_address")
        if amount <= 0:
            raise StateError("amount must be > 0")
        # Phase 18: BRIDGE_MINT recipient may be either m0r-native or 0x-legacy
        # (EVM-bridged accounts originally used 0x). parse_address accepts both.
        try:
            crypto.parse_address(recipient)
        except Exception:
            raise StateError(
                "recipient must be m0r-prefixed (native) or 0x-prefixed (legacy)")
        if c.execute("SELECT 1 FROM bridge_mints WHERE evm_lock_id=?",
                     (evm_id,)).fetchone():
            raise StateError("evm_lock_id already minted")
        self._ensure_account(c, recipient)

        if token == "MORM":
            bal = c.execute("SELECT balance FROM accounts WHERE address=?",
                            (self.treasury,)).fetchone()[0]
            if bal < amount:
                raise StateError("treasury insufficient (MORM cap reached)")
            c.execute("UPDATE accounts SET balance=balance-? WHERE address=?",
                      (amount, self.treasury))
            c.execute("UPDATE accounts SET balance=balance+? WHERE address=?",
                      (amount, recipient))
        else:
            # ERC-20 mirror — no cap, balance lives in account_tokens
            c.execute(
                "INSERT INTO account_tokens (address, token, balance) VALUES (?, ?, ?) "
                "ON CONFLICT(address, token) DO UPDATE SET balance = balance + excluded.balance",
                (recipient, token, amount),
            )
        c.execute(
            "INSERT INTO bridge_mints (evm_lock_id, recipient, amount, minted_at) "
            "VALUES (?, ?, ?, ?)",
            (evm_id, recipient, amount, ts),
        )

    def _tx_bridge_burn(self, c, sender: str, tx: Transaction, ts: int):
        """Burn caller's L1 balance (native or token) and record the EVM
        recipient + token info. The relayer reads bridge_burns off-chain and
        calls the matching unlock function on the appropriate EVM bridge."""
        p = tx.payload
        amount = int(p["amount"])
        evm_recipient = p["evm_recipient"]
        token = p.get("token", "MORM")
        token_address = p.get("token_address")
        if amount <= 0:
            raise StateError("amount must be > 0")
        if not (evm_recipient.startswith("0x") and len(evm_recipient) == 42):
            raise StateError("evm_recipient must be 0x + 40 hex")
        if token == "MORM":
            bal = c.execute("SELECT balance FROM accounts WHERE address=?",
                            (sender,)).fetchone()[0]
            if bal < amount:
                raise StateError("insufficient MORM balance to burn")
            c.execute("UPDATE accounts SET balance=balance-? WHERE address=?",
                      (amount, sender))
            c.execute("UPDATE accounts SET balance=balance+? WHERE address=?",
                      (amount, self.treasury))
        else:
            row = c.execute(
                "SELECT balance FROM account_tokens WHERE address=? AND token=?",
                (sender, token),
            ).fetchone()
            tbal = row[0] if row else 0
            if tbal < amount:
                raise StateError(f"insufficient {token} balance to burn")
            c.execute(
                "UPDATE account_tokens SET balance=balance-? WHERE address=? AND token=?",
                (amount, sender, token),
            )
        c.execute(
            "INSERT INTO bridge_burns (burn_tx_hash, burner, amount, evm_recipient, "
            "token, token_address, evm_unlocked, burned_at) "
            "VALUES (?, ?, ?, ?, ?, ?, 0, ?)",
            (tx.hash().hex(), sender, amount, evm_recipient, token, token_address, ts),
        )

    def _tx_view_reward(self, c, sender: str, tx: Transaction, ts: int):
        """Per-cell view reward. Spec MORM.md §3 — 'viewer becomes a relay,
        microtoken accumulates passively'. We model it as a treasury subsidy
        gated on uniqueness."""
        cid = tx.payload["content_id"]
        idx = int(tx.payload["cell_index"])
        if idx < 0:
            raise StateError("cell_index must be >= 0")
        if not c.execute("SELECT 1 FROM contents WHERE content_id=?",
                         (cid,)).fetchone():
            raise StateError("unknown content")
        if c.execute(
            "SELECT 1 FROM views WHERE viewer=? AND content_id=? AND cell_index=?",
            (sender, cid, idx),
        ).fetchone():
            raise StateError("already rewarded for this view")
        # subsidy from treasury — bounded supply, fails if treasury empty
        bal = c.execute("SELECT balance FROM accounts WHERE address=?",
                        (self.treasury,)).fetchone()[0]
        if bal < VIEW_REWARD_AMOUNT:
            raise StateError("treasury exhausted")
        c.execute("UPDATE accounts SET balance=balance-? WHERE address=?",
                  (VIEW_REWARD_AMOUNT, self.treasury))
        c.execute("UPDATE accounts SET balance=balance+? WHERE address=?",
                  (VIEW_REWARD_AMOUNT, sender))
        c.execute(
            "INSERT INTO views (viewer, content_id, cell_index, rewarded_at) "
            "VALUES (?, ?, ?, ?)",
            (sender, cid, idx, ts),
        )

    def _tx_transfer(self, c, sender: str, tx: Transaction):
        to = tx.payload["to"]
        amount = int(tx.payload["amount"])
        if amount <= 0:
            raise StateError("amount must be > 0")
        # Phase 18: accept both m0r-prefixed (native) and 0x (legacy/EVM bytes20).
        try:
            crypto.parse_address(to)
        except Exception:
            raise StateError(
                "recipient must be m0r-prefixed (native) or 0x-prefixed (legacy)")
        bal = c.execute("SELECT balance FROM accounts WHERE address=?",
                        (sender,)).fetchone()[0]
        if bal < amount:
            raise StateError("insufficient balance")
        # ensure recipient row exists
        self._ensure_account(c, to)
        # check recipient lock — refuse to send to locked accounts (anti-funding)
        row = c.execute("SELECT locked FROM accounts WHERE address=?", (to,)).fetchone()
        if row[0]:
            raise StateError("recipient is locked")
        c.execute("UPDATE accounts SET balance=balance-? WHERE address=?", (amount, sender))
        c.execute("UPDATE accounts SET balance=balance+? WHERE address=?", (amount, to))

    # -- PoUW handlers ----------------------------------------------------

    def _tx_post_job(self, c, sender: str, tx: Transaction, ts: int):
        p = tx.payload
        jid, cid, kind, reward = p["job_id"], p["content_id"], p["kind"], int(p["reward"])
        if reward <= 0:
            raise StateError("reward must be > 0")
        if c.execute("SELECT 1 FROM jobs WHERE job_id=?", (jid,)).fetchone():
            raise StateError("job already exists")
        if not c.execute("SELECT 1 FROM contents WHERE content_id=?", (cid,)).fetchone():
            raise StateError("unknown content")
        bal = c.execute("SELECT balance FROM accounts WHERE address=?",
                        (sender,)).fetchone()[0]
        if bal < reward:
            raise StateError("insufficient balance to fund reward")
        # lock reward in escrow
        c.execute("UPDATE accounts SET balance=balance-? WHERE address=?",
                  (reward, sender))
        self._ensure_account(c, ESCROW_ACCOUNT)
        c.execute("UPDATE accounts SET balance=balance+? WHERE address=?",
                  (reward, ESCROW_ACCOUNT))
        c.execute(
            "INSERT INTO jobs (job_id, content_id, kind, poster, reward, status, posted_at) "
            "VALUES (?, ?, ?, ?, ?, 1, ?)",
            (jid, cid, kind, sender, reward, ts),
        )

    def _tx_claim_job(self, c, sender: str, tx: Transaction):
        jid = tx.payload["job_id"]
        row = c.execute("SELECT status, claimer FROM jobs WHERE job_id=?",
                        (jid,)).fetchone()
        if not row:
            raise StateError("unknown job")
        if row[0] != 1:
            raise StateError(f"job not claimable (status={row[0]})")
        c.execute("UPDATE jobs SET claimer=?, status=2 WHERE job_id=?", (sender, jid))

    def _tx_submit_work_proof(self, c, sender: str, tx: Transaction):
        p = tx.payload
        jid, output_root = p["job_id"], p["output_root"]
        row = c.execute(
            "SELECT status, claimer, reward FROM jobs WHERE job_id=?", (jid,)
        ).fetchone()
        if not row:
            raise StateError("unknown job")
        status, claimer, reward = row
        if status != 2:
            raise StateError(f"job not in claimed state (status={status})")
        if claimer != sender:
            raise StateError("only the claimer can submit work proof")
        # release reward from escrow → worker
        c.execute("UPDATE accounts SET balance=balance-? WHERE address=?",
                  (reward, ESCROW_ACCOUNT))
        c.execute("UPDATE accounts SET balance=balance+? WHERE address=?",
                  (reward, sender))
        c.execute(
            "UPDATE jobs SET output_root=?, status=3 WHERE job_id=?",
            (output_root, jid),
        )
        # bump worker reputation
        c.execute(
            "INSERT INTO worker_stats (address, completed, earned) VALUES (?, 1, ?) "
            "ON CONFLICT(address) DO UPDATE SET "
            "  completed = completed + 1, earned = earned + excluded.earned",
            (sender, reward),
        )

    # ---- introspection ------------------------------------------------------

    def _compute_state_root(self, c) -> bytes:
        """Deterministic snapshot — hash of every table sorted by primary key."""
        h = hashlib.sha256()
        for table, cols in (
            ("contents", "content_id,root_hash,generation_id,creator,registered_at"),
            ("orders", "order_id,content_id,buyer,seller,amount,fee,packing_hash,opening_hash,status,created_at"),
            ("accounts", "address,nonce,balance,stake,locked"),
            ("jobs", "job_id,content_id,kind,poster,reward,claimer,output_root,status,posted_at"),
            ("worker_stats", "address,completed,earned"),
            ("views", "viewer,content_id,cell_index,rewarded_at"),
            ("bridge_mints", "evm_lock_id,recipient,amount,minted_at"),
            ("bridge_burns", "burn_tx_hash,burner,amount,evm_recipient,token,token_address,evm_unlocked,burned_at"),
            ("account_tokens", "address,token,balance"),
            ("ai_services", "pubkey,name,registered_at"),
            ("producers", "pubkey,address,name,registered_at"),
            ("treasury_signers", "pubkey,name,registered_at"),
            ("treasury_config", "rowid,threshold,n_signers,enabled,enabled_at"),
        ):
            rows = c.execute(f"SELECT {cols} FROM {table} ORDER BY 1").fetchall()
            for r in rows:
                h.update(table.encode())
                h.update(json.dumps(r, sort_keys=True, separators=(",", ":"),
                                     default=str).encode())
        return h.digest()

    # public helpers
    def state_root(self) -> bytes:
        c = self._conn()
        try:
            return self._compute_state_root(c)
        finally:
            c.close()

    def get_account(self, address: str) -> dict:
        """Read-only account lookup.

        IMPORTANT (Phase 24b correctness): MUST NOT mutate state. Earlier
        revisions called `_ensure_account` here, which on every `/account/X`
        HTTP read would INSERT a zero-balance row into the persistent
        accounts table. Under DAG-mode (Phase 24b) the materialized state
        is supposed to be byte-exact equal to the canonical replay of the
        DAG; any read-side INSERT silently drifts it (an unused address
        appears in `accounts`, `_compute_state_root` hashes the extra row,
        nodes diverge). The fix: return zeros if the address has never
        been touched by a tx, instead of materializing a row."""
        c = self._conn()
        try:
            row = c.execute(
                "SELECT nonce, balance, stake, locked FROM accounts WHERE address=?",
                (address,)
            ).fetchone()
            if row is None:
                row = (0, 0, 0, 0)
            tokens = {
                t: b for t, b in c.execute(
                    "SELECT token, balance FROM account_tokens WHERE address=?",
                    (address,),
                ).fetchall()
            }
            return {"address": address, "nonce": row[0], "balance": row[1],
                    "stake": row[2], "locked": bool(row[3]),
                    "tokens": tokens}
        finally:
            c.close()

    def get_content(self, cid: str) -> dict | None:
        c = self._conn()
        try:
            row = c.execute(
                "SELECT content_id, root_hash, generation_id, creator, registered_at "
                "FROM contents WHERE content_id=?", (cid,)
            ).fetchone()
            if not row:
                return None
            return {
                "content_id": row[0], "root_hash": row[1],
                "generation_id": row[2], "creator": row[3],
                "registered_at": row[4],
            }
        finally:
            c.close()

    def get_order(self, oid: str) -> dict | None:
        c = self._conn()
        try:
            row = c.execute(
                "SELECT order_id, content_id, buyer, seller, amount, fee, "
                "packing_hash, opening_hash, status, created_at "
                "FROM orders WHERE order_id=?", (oid,)
            ).fetchone()
            if not row:
                return None
            return dict(zip(
                ["order_id","content_id","buyer","seller","amount","fee",
                 "packing_hash","opening_hash","status","created_at"], row))
        finally:
            c.close()

    def get_job(self, jid: str) -> dict | None:
        c = self._conn()
        try:
            row = c.execute(
                "SELECT job_id, content_id, kind, poster, reward, claimer, output_root, status, posted_at "
                "FROM jobs WHERE job_id=?", (jid,)
            ).fetchone()
            if not row:
                return None
            return dict(zip(
                ["job_id","content_id","kind","poster","reward","claimer",
                 "output_root","status","posted_at"], row))
        finally:
            c.close()

    def list_jobs(self, status: int | None = None, limit: int = 50) -> list[dict]:
        c = self._conn()
        try:
            if status is None:
                rows = c.execute(
                    "SELECT job_id,content_id,kind,poster,reward,claimer,output_root,status,posted_at "
                    "FROM jobs ORDER BY posted_at DESC LIMIT ?", (limit,)
                ).fetchall()
            else:
                rows = c.execute(
                    "SELECT job_id,content_id,kind,poster,reward,claimer,output_root,status,posted_at "
                    "FROM jobs WHERE status=? ORDER BY posted_at DESC LIMIT ?",
                    (status, limit),
                ).fetchall()
            keys = ["job_id","content_id","kind","poster","reward","claimer",
                    "output_root","status","posted_at"]
            return [dict(zip(keys, r)) for r in rows]
        finally:
            c.close()

    def list_producers(self) -> list[dict]:
        """All registered producers with their PoUW-derived weight."""
        c = self._conn()
        try:
            rows = c.execute(
                "SELECT p.pubkey, p.address, p.name, p.registered_at, "
                "  COALESCE(w.completed, 0) AS completed "
                "FROM producers p "
                "LEFT JOIN worker_stats w ON w.address = p.address "
                "ORDER BY p.registered_at"
            ).fetchall()
            out = []
            for r in rows:
                out.append({
                    "pubkey": r[0], "address": r[1], "name": r[2],
                    "registered_at": r[3], "completed": r[4],
                    "weight": 1 + int(r[4]),   # base 1 + jobs done
                })
            return out
        finally:
            c.close()

    def slot_owner(self, height: int) -> dict | None:
        """Deterministic slot owner for `height`. None if no producers."""
        producers = self.list_producers()
        if not producers:
            return None
        weights = [p["weight"] for p in producers]
        total = sum(weights)
        # use blake2b for cross-platform determinism (no Python hash() salt)
        import hashlib as _h
        digest = _h.blake2b(b"morm-slot|" + str(height).encode(),
                            digest_size=8).digest()
        idx = int.from_bytes(digest, "big") % total
        cum = 0
        for p in producers:
            cum += p["weight"]
            if idx < cum:
                return p
        return producers[-1]

    def get_worker_stats(self, addr: str) -> dict:
        c = self._conn()
        try:
            row = c.execute(
                "SELECT completed, earned FROM worker_stats WHERE address=?",
                (addr,),
            ).fetchone()
            return {"address": addr,
                    "completed": row[0] if row else 0,
                    "earned": row[1] if row else 0}
        finally:
            c.close()

    def latest_blocks(self, n: int = 10) -> list[dict]:
        c = self._conn()
        try:
            rows = c.execute(
                "SELECT hash, height, parents, producer, state_root "
                "FROM blocks ORDER BY height DESC LIMIT ?", (n,)
            ).fetchall()
            return [
                {"hash": r[0], "height": r[1],
                 "parents": json.loads(r[2]),
                 "producer": r[3], "state_root": r[4]}
                for r in rows
            ]
        finally:
            c.close()

    def tip_hashes(self) -> list[bytes]:
        """Return the highest-height block hashes (1+ if forks; PoC: just 1)."""
        c = self._conn()
        try:
            row = c.execute("SELECT MAX(height) FROM blocks").fetchone()
            if not row or row[0] is None:
                from . import GENESIS_HASH
                return [GENESIS_HASH]
            tips = c.execute("SELECT hash FROM blocks WHERE height = ?", (row[0],)).fetchall()
            return [bytes.fromhex(t[0]) for t in tips]
        finally:
            c.close()


def _ts() -> int:
    import time
    return int(time.time() * 1000)
