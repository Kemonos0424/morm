"""Producer loop + gossip: a MORM L1 node.

Phase 10c upgrade: each node also has a peer list. After producing a block
the producer fan-outs the serialized block to every peer over HTTP (which
in production would be QUIC; the surface area is the same — POST a payload,
peer validates + applies). Receivers don't re-execute the block from
scratch — they just validate signatures + state_root locally.
"""
from __future__ import annotations

import json
import sys
import threading
import time
import urllib.error
import urllib.request
from collections import deque
from pathlib import Path

from . import crypto
from .block import Block, BlockHeader, compute_tx_root
from .state import State
from .tx import Transaction


import os as _os
# BLOCK_INTERVAL is exposed via env var so Phase 24a verification can crank
# it down (e.g. MORM_BLOCK_INTERVAL=0.05) to force DAG widening — under
# normal LAN gossip latency, 1 s is too slow to ever produce siblings.
BLOCK_INTERVAL = float(_os.environ.get("MORM_BLOCK_INTERVAL", "1.0"))

# Phase 26c: mempool flood DoS defenses (SECURITY-DESIGN §1.1 26c).
# - MEMPOOL_MAX_TXS  — hard cap on total queued tx; further submits get
#   rejected by submit_tx until existing tx are sealed or pruned. Without
#   this, a script-kiddie can OOM the node by signing valid TRANSFER tx in
#   a tight loop.
# - MEMPOOL_MAX_PER_SENDER — per-sender quota. The chain has no fee
#   mechanism (Whitepaper §9.1: 1 µMORM minted per cell view, never spent),
#   so we approximate "fee floor" with a hard per-sender cap on pending tx.
#   A single rogue sender can occupy at most 32 mempool slots; honest
#   senders keep room.
# Both can be overridden per-node via Node(...) kwargs / `--mempool-max-*`
# CLI flags so smoke tests / multi-tenant deployments can tune separately.
MEMPOOL_MAX_TXS_DEFAULT       = 5000
MEMPOOL_MAX_PER_SENDER_DEFAULT = 32


class Node:
    def __init__(self, data_dir: Path, producer_seed: bytes, treasury_address: str,
                 peers: list[str] | None = None, produce: bool = True,
                 dag_mode: bool = False, quic: bool = False,
                 mempool_max_txs: int = MEMPOOL_MAX_TXS_DEFAULT,
                 mempool_max_per_sender: int = MEMPOOL_MAX_PER_SENDER_DEFAULT,
                 genesis_lockdown_height: int | None = None):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        # Phase 24a: dag_mode propagates to State so apply_block tolerates
        # multi-tip / sibling divergence; produce_one drops slot election.
        self.dag_mode = dag_mode
        # Phase 26e — pass the lockdown height through to State; None means
        # use the State default (100).
        state_kwargs = {"treasury": treasury_address, "dag_mode": dag_mode}
        if genesis_lockdown_height is not None:
            state_kwargs["genesis_lockdown_height"] = genesis_lockdown_height
        self.state = State(self.data_dir / "state.db", **state_kwargs)
        self.producer_seed = producer_seed
        self.producer_pub = crypto.pubkey_from_seed(producer_seed)
        self.mempool: deque[Transaction] = deque()
        # Phase 26c — DoS guards. Configurable per-node via Node ctor.
        self.mempool_max_txs       = int(mempool_max_txs)
        self.mempool_max_per_sender = int(mempool_max_per_sender)
        # Counters for fast cap checks. Updated whenever mempool changes.
        self._sender_count: dict[bytes, int] = {}
        self.peers: list[str] = list(peers or [])
        self.produce_enabled = produce
        self._seen_blocks: set[bytes] = set()
        self._seen_txs: set[bytes] = set()
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._producer_thread: threading.Thread | None = None

        # Phase 25a: optional QUIC transport. Fanout becomes hybrid —
        # peers advertising `quic_cert_pin` in /info get blocks/txs over
        # QUIC; the rest stay on HTTP gossip. Cert pin cache is refreshed
        # lazily when the first send to a peer happens.
        self.quic_enabled = quic
        self.quic_cert_path = None
        self.quic_cert_pin = None
        self.quic_runtime = None
        self._peer_quic_cache: dict[str, dict] = {}   # peer_url -> {pin, host, port, ttl_ts}
        self._peer_quic_cache_lock = threading.Lock()

    # ---- mempool ----------------------------------------------------------

    def submit_tx(self, tx: Transaction, gossip: bool = True) -> bool:
        if not tx.verify():
            return False
        h = tx.hash()
        with self._lock:
            if h in self._seen_txs:
                return True
            # Phase 26c: enforce DoS caps BEFORE accepting into the mempool.
            # We check global cap first (cheap O(1)), then per-sender cap.
            # On reject we deliberately do NOT mark `_seen_txs` so a polite
            # retry after the queue drains is accepted normally.
            if len(self.mempool) >= self.mempool_max_txs:
                sys.stderr.write(
                    f"[mempool] reject: global cap reached "
                    f"({len(self.mempool)}/{self.mempool_max_txs})\n")
                return False
            sender_n = self._sender_count.get(tx.sender, 0)
            if sender_n >= self.mempool_max_per_sender:
                sys.stderr.write(
                    f"[mempool] reject: per-sender cap reached for "
                    f"{tx.sender.hex()[:8]}… "
                    f"({sender_n}/{self.mempool_max_per_sender})\n")
                return False
            self._seen_txs.add(h)
            self.mempool.append(tx)
            self._sender_count[tx.sender] = sender_n + 1
        if gossip:
            self._fanout_tx(tx)
        return True

    def drain_mempool(self) -> list[Transaction]:
        with self._lock:
            txs = list(self.mempool)
            self.mempool.clear()
            self._sender_count.clear()   # Phase 26c
            return txs

    # ---- producer ---------------------------------------------------------

    def produce_one(self) -> Block | None:
        height_row = self.state._conn().execute(
            "SELECT MAX(height) FROM blocks"
        ).fetchone()
        height = (height_row[0] or 0) + 1
        parents = self.state.tip_hashes()

        # Phase 26e — Genesis lockdown: while no producer is registered AND
        # we're below the lockdown ceiling, only the treasury holder may
        # produce. Without this, an attacker spawning a node early can
        # eclipse the chain with self-produced blocks before the operator
        # registers a real producer. Apply ALSO catches imported blocks
        # (state.apply_block guard); this gate just stops self-production.
        if self.state.genesis_lockdown_active(height):
            if crypto.address(self.producer_pub) != self.state.treasury:
                return None      # not treasury — wait for treasury or producers

        # Phase 17a: only the elected slot owner produces this height.
        # If no producers registered yet (genesis bootstrap), every node may
        # produce — preserves single-node behaviour for early Phases.
        # Phase 24a/b: when dag_mode is on, drop the slot gate entirely so
        # every registered producer can seal in parallel.
        if not self.dag_mode:
            slot = self.state.slot_owner(height)
            if slot is not None and slot["pubkey"] != self.producer_pub.hex():
                return None      # not my slot — wait for the rightful producer

        txs = self.drain_mempool()
        if not txs:
            return None

        # signature pre-filter (cheap, no state needed)
        for tx in list(txs):
            try:
                if not tx.verify():
                    txs.remove(tx)
            except Exception:
                txs.remove(tx)
        if not txs:
            return None

        block_ts = int(time.time() * 1000)

        if self.dag_mode:
            return self._produce_dag(parents, height, txs, block_ts)
        return self._produce_single_chain(parents, height, txs, block_ts)

    def _produce_single_chain(self, parents, height, txs, block_ts) -> Block | None:
        """Phase 17 path: apply directly to materialized state, sign, persist."""
        applied: list[Transaction] = []
        c = self.state._conn()
        c.execute("BEGIN IMMEDIATE")
        try:
            for tx in txs:
                try:
                    self.state._apply_tx(c, tx, block_ts=block_ts)
                    applied.append(tx)
                except Exception as e:
                    sys.stderr.write(f"[producer] tx rejected: {type(e).__name__}: {e}\n")
            if not applied:
                c.execute("ROLLBACK")
                return None
            state_root = self.state._compute_state_root(c)
            tx_root = compute_tx_root(applied)

            header = BlockHeader(
                height=height,
                parent_hashes=parents,
                producer=self.producer_pub,
                timestamp=block_ts,
                state_root=state_root,
                tx_root=tx_root,
            )
            block = Block(header, applied).sign(self.producer_seed)

            c.execute(
                "INSERT INTO blocks (hash, height, parents, producer, state_root, payload) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (block.hash().hex(), height,
                 json.dumps([h.hex() for h in parents]),
                 self.producer_pub.hex(), state_root.hex(),
                 json.dumps(block.to_dict())),
            )
            c.execute("COMMIT")
            self._seen_blocks.add(block.hash())
            self._fanout_block(block)
            return block
        except Exception:
            c.execute("ROLLBACK")
            raise
        finally:
            c.close()

    def _produce_dag(self, parents, height, txs, block_ts) -> Block | None:
        """Phase 24b path: compute state_root via canonical replay of parent
        frontier + my candidate txs. Persist via apply_block which rebuilds
        the materialized state from the new canonical frontier."""
        try:
            applied, state_root = self.state.replay_with_filter(
                parents, txs, block_ts)
        except Exception as e:
            sys.stderr.write(f"[24b producer] replay failed: {e}\n")
            self._reinsert_mempool(txs)
            return None
        # Re-queue any candidate tx that didn't apply this round so it gets
        # another chance once its predecessors land. Without this, drain_mempool
        # would silently drop nonce-gapped or sibling-sealed txs and the chain
        # would underutilize the senders' load.
        if len(applied) < len(txs):
            applied_hashes = {tx.hash() for tx in applied}
            unapplied = [tx for tx in txs if tx.hash() not in applied_hashes]
            self._reinsert_mempool(unapplied)
        if not applied:
            return None

        header = BlockHeader(
            height=height,
            parent_hashes=parents,
            producer=self.producer_pub,
            timestamp=block_ts,
            state_root=state_root,
            tx_root=compute_tx_root(applied),
        )
        block = Block(header, applied).sign(self.producer_seed)

        # Mark seen BEFORE persistence so a self-import via gossip is a no-op.
        self._seen_blocks.add(block.hash())
        try:
            self.state.apply_block(block)   # 24b strict verify + materialize
        except Exception as e:
            sys.stderr.write(f"[24b producer] self-apply failed: {e}\n")
            self._seen_blocks.discard(block.hash())
            # Phase 24d-aware: a self-apply failure (e.g. rate-limit
            # rejection) must not drop the txs we already drained — they're
            # still valid for the next round. Without this restore, the
            # rate-limited producer silently loses every tx in its queue.
            self._reinsert_mempool(applied)
            return None
        self._fanout_block(block)
        return block

    def _reinsert_mempool(self, txs):
        """Put back txs that drain_mempool removed but the producer didn't seal,
        preserving their original order so dependent-nonce tx chains can land
        in subsequent rounds. Drops txs already known sealed (defensive).

        Phase 26c — caps are NOT re-enforced here: these are tx that already
        passed submit_tx once. Refusing them now would drop honest work and
        break dependent-nonce chains. Caps only gate fresh submissions."""
        if not txs:
            return
        with self._lock:
            existing = {tx.hash() for tx in self.mempool}
            for tx in reversed(txs):
                h = tx.hash()
                if h in existing:
                    continue
                self.mempool.appendleft(tx)
                existing.add(h)
                self._sender_count[tx.sender] = self._sender_count.get(tx.sender, 0) + 1

    def start_producer(self):
        if not self.produce_enabled:
            print("[producer] disabled (passive node)")
            return

        def loop():
            while not self._stop.is_set():
                try:
                    blk = self.produce_one()
                    if blk:
                        sys.stderr.write(
                            f"[producer] sealed #{blk.header.height} "
                            f"hash={blk.hash().hex()[:16]}… "
                            f"txs={len(blk.transactions)}\n"
                        )
                except Exception as e:
                    sys.stderr.write(f"[producer] error: {e}\n")
                self._stop.wait(BLOCK_INTERVAL)

        self._producer_thread = threading.Thread(target=loop, daemon=True)
        self._producer_thread.start()

    # ---- gossip + import --------------------------------------------------

    def import_block(self, block: Block, gossip: bool = True) -> bool:
        """Apply an externally-produced block. Returns True if newly imported."""
        bh = block.hash()
        with self._lock:
            if bh in self._seen_blocks:
                return False
            self._seen_blocks.add(bh)
        if not block.verify():
            sys.stderr.write(f"[import] block {bh.hex()[:16]}… signature/tx invalid\n")
            return False
        try:
            self.state.apply_block(block)
        except Exception as e:
            sys.stderr.write(f"[import] apply failed: {e}\n")
            return False
        # Phase 23a: prune mempool of txs the imported block already includes,
        # otherwise this node's next slot drains stale-nonce txs and produces
        # nothing. Without this, only the RPC-receiving node ever balances.
        included = {tx.hash() for tx in block.transactions}
        with self._lock:
            kept = deque(
                tx for tx in self.mempool if tx.hash() not in included)
            self.mempool = kept
            # Phase 26c: rebuild per-sender count from the survivors so the
            # cap reflects the post-prune state. Without this, the counter
            # drifts upward forever and submit_tx eventually rejects honest
            # senders even when their pending tx have all been sealed.
            self._sender_count = {}
            for t in kept:
                self._sender_count[t.sender] = self._sender_count.get(t.sender, 0) + 1
        sys.stderr.write(
            f"[import] applied #{block.header.height} hash={bh.hex()[:16]}… "
            f"from={crypto.address(block.header.producer)[:10]}… "
            f"pruned_mempool_to={len(self.mempool)}\n"
        )
        if gossip:
            self._fanout_block(block)
        return True

    def sync_from_peers(self):
        """Pull blocks we don't have from peers (one-shot)."""
        my_height = self._max_height()
        for peer in self.peers:
            try:
                info = self._peer_get(peer, "/info")
                latest = info.get("latest", [])
                peer_height = latest[0]["height"] if latest else 0
                while my_height < peer_height:
                    nxt = my_height + 1
                    blocks = self._peer_get(peer, f"/blocks/at/{nxt}")
                    if not blocks.get("blocks"):
                        break
                    for raw in blocks["blocks"]:
                        b = Block.from_dict(raw)
                        if self.import_block(b, gossip=False):
                            my_height = b.header.height
            except Exception as e:
                sys.stderr.write(f"[sync] {peer}: {e}\n")
                continue

    def _max_height(self) -> int:
        c = self.state._conn()
        try:
            row = c.execute("SELECT MAX(height) FROM blocks").fetchone()
            return row[0] or 0
        finally:
            c.close()

    def _fanout_block(self, block: Block):
        # Phase 25c: gossip is QUIC-only. If the peer doesn't advertise a
        # quic_cert_pin we log + drop — there is no HTTP fallback. Old
        # nodes that haven't upgraded to --quic stay out of the gossip
        # mesh (they can still serve their own RPC).
        block_dict = block.to_dict()
        for peer in self.peers:
            if not self._fanout_via_quic(peer, "block", block_dict):
                sys.stderr.write(
                    f"[gossip] DROP block → {peer}: peer has no "
                    f"quic_cert_pin (Phase 25c removed HTTP gossip)\n")

    def _fanout_tx(self, tx: Transaction):
        tx_dict = tx.to_dict()
        for peer in self.peers:
            if not self._fanout_via_quic(peer, "tx", tx_dict):
                sys.stderr.write(
                    f"[gossip] DROP tx → {peer}: peer has no "
                    f"quic_cert_pin (Phase 25c removed HTTP gossip)\n")

    def _fanout_via_quic(self, peer: str, kind: str, payload: dict) -> bool:
        """Phase 25a hybrid fanout. Returns True if the message was scheduled
        on the QUIC runtime (caller should NOT also POST it via HTTP);
        returns False to indicate fallback to HTTP gossip.

        Lazily probes the peer's `/info` for `quic_cert_pin`; cached for
        60 s. If the peer advertises QUIC, host+port are pulled from the
        peer URL and the QUIC client schedules a fire-and-forget send.
        TOFU: we accept the first pin we see; mismatch on subsequent
        probes drops the cache + falls back to HTTP for one round."""
        if not self.quic_enabled or self.quic_runtime is None:
            return False
        info = self._peer_quic_info(peer)
        if not info or not info.get("pin"):
            return False
        try:
            # Phase 25b: block fanout schedules a compact binary
            # block-header datagram (DAG-DESIGN §7, ~370 B for 3 parents)
            # *plus* the full JSON body via a reliable stream. The
            # datagram is the fast announcement path — receivers learn
            # the new block hash immediately and can dedupe; the stream
            # carries the body for the actual import_block. txs always
            # go via streams (reliable, ordered).
            prefer_datagram = (kind == "block")
            self.quic_runtime.schedule_send(
                info["host"], info["port"], kind, payload,
                prefer_datagram=prefer_datagram,
            )
            sys.stderr.write(
                f"[quic-fanout] {kind} → {peer} (pin={info['pin']})\n")
            return True
        except Exception as e:
            sys.stderr.write(
                f"[quic-fanout] schedule failed for {peer}: {e}\n")
            return False

    def _peer_quic_info(self, peer: str) -> dict | None:
        """Cached `(pin, host, port)` for `peer`. Probes /info on first use
        and re-probes after 60 s. Returns None if peer is non-QUIC or
        unreachable."""
        import time
        with self._peer_quic_cache_lock:
            cached = self._peer_quic_cache.get(peer)
            if cached and cached.get("ttl_ts", 0) > time.time():
                return cached
        try:
            info = self._peer_get(peer, "/info")
        except Exception:
            return None
        pin = info.get("quic_cert_pin")
        host, port = self._peer_host_port(peer)
        if not pin or host is None:
            entry = {"pin": None, "host": None, "port": None,
                     "ttl_ts": time.time() + 60}
        else:
            entry = {"pin": pin, "host": host, "port": port,
                     "ttl_ts": time.time() + 60}
        with self._peer_quic_cache_lock:
            self._peer_quic_cache[peer] = entry
        return entry if entry.get("pin") else None

    @staticmethod
    def _peer_host_port(peer: str) -> tuple:
        """Parse 'http://host:port' (or 'http://host') into (host, port)."""
        from urllib.parse import urlparse
        u = urlparse(peer)
        if not u.hostname:
            return (None, None)
        port = u.port or (443 if u.scheme == "https" else 80)
        return (u.hostname, port)

    def _peer_post_async(self, peer: str, path: str, body: bytes):
        # fire-and-forget on a background thread so producer doesn't block
        def go():
            try:
                req = urllib.request.Request(
                    peer.rstrip("/") + path, method="POST",
                    data=body, headers={"Content-Type": "application/json"},
                )
                urllib.request.urlopen(req, timeout=2).read()
            except (urllib.error.URLError, TimeoutError):
                pass
        threading.Thread(target=go, daemon=True).start()

    def _peer_get(self, peer: str, path: str) -> dict:
        with urllib.request.urlopen(peer.rstrip("/") + path, timeout=2) as r:
            return json.loads(r.read())

    def stop(self):
        self._stop.set()
        if self._producer_thread:
            self._producer_thread.join(timeout=2)
