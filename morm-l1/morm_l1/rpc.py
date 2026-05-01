"""HTTP RPC for a MORM L1 node.

  POST /tx                      submit signed tx (json body)
  GET  /block/{hash}            block by hash
  GET  /blocks/latest?n=10      recent blocks
  GET  /tip                     current DAG tips
  GET  /account/{addr}          balance / nonce / stake / locked
  GET  /content/{cid}           content record
  GET  /order/{oid}             order record
  GET  /info                    node identity + state_root
"""
from __future__ import annotations

import json
import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import crypto
from .block import Block
from .node import Node
from .tx import Transaction


class Handler(BaseHTTPRequestHandler):
    server_version = "MORM-L1/0.1"

    def log_message(self, fmt, *args):
        sys.stderr.write(f"[rpc] {fmt % args}\n")

    # Same DNS-hang reason as RpcServer.server_bind: BaseHTTPRequestHandler's
    # default address_string() calls socket.getfqdn(client_ip) which blocks
    # 35s per request on Mac Mini Tahoe. We just return the IP literal.
    def address_string(self):
        host, _ = self.client_address[:2]
        return host

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self):
        self.send_response(204); self._cors(); self.end_headers()

    def _json(self, status, body):
        data = json.dumps(body, ensure_ascii=False, default=str).encode()
        self.send_response(status); self._cors()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _read_json(self):
        n = int(self.headers.get("Content-Length", "0") or 0)
        return json.loads(self.rfile.read(n).decode()) if n else {}

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        node: Node = self.server.node

        if path == "/info":
            from . import FINALITY_DEPTH
            latest = node.state.latest_blocks(1)
            head = latest[0]["height"] if latest else 0
            # Phase 24c: DAG-mode nodes use common-ancestor finality instead
            # of head-K. A block is finalized once every current tip builds
            # on top of it AND the tip count meets the ⅔-of-producers witness
            # threshold. This is tighter (single-block) when producers are
            # online and uniformly building, and freezes (returns 0) when a
            # partition splits witnesses below threshold.
            if node.dag_mode:
                finalized = node.state.finalized_height_dag()
                finality_label = "common-ancestor (Phase 24c)"
            else:
                finalized = max(0, head - FINALITY_DEPTH)
                finality_label = f"head − {FINALITY_DEPTH} (Phase 17b)"
            # Phase 24a: surface DAG metrics so /admin and 3-node tests can
            # observe how wide the chain has grown under concurrent sealing.
            c = node.state._conn()
            try:
                row = c.execute(
                    "SELECT MAX(cnt) FROM "
                    "(SELECT COUNT(*) AS cnt FROM blocks GROUP BY height)"
                ).fetchone()
                max_dag_width = row[0] or 1
                row2 = c.execute(
                    "SELECT COUNT(*) FROM blocks WHERE height = ?", (head,)
                ).fetchone()
                head_width = row2[0] or 1
            finally:
                c.close()
            return self._json(200, {
                "producer": node.producer_pub.hex(),
                "producer_address": crypto.address(node.producer_pub),
                "treasury": node.state.treasury,
                "state_root": node.state.state_root().hex(),
                "tips": [h.hex() for h in node.state.tip_hashes()],
                "mempool": len(node.mempool),
                # Phase 26c: surface mempool DoS caps so clients (and
                # operators) can see whether their tx submission was
                # bounced by quota vs by validation.
                "mempool_max_txs": node.mempool_max_txs,
                "mempool_max_per_sender": node.mempool_max_per_sender,
                # Phase 26e: surface the genesis lockdown ceiling AND
                # whether it is currently active so peers know why a
                # non-treasury producer's blocks would be rejected.
                "genesis_lockdown_height": node.state.genesis_lockdown_height,
                "genesis_lockdown_active": node.state.genesis_lockdown_active(head + 1),
                "latest": latest,
                "head_height": head,
                "finalized_height": finalized,
                "finality_depth": FINALITY_DEPTH,
                "finality_rule": finality_label,
                "producers": node.state.list_producers(),
                "next_slot_owner": node.state.slot_owner(head + 1),
                "dag_mode": node.dag_mode,
                "dag_max_width": max_dag_width,    # widest height in chain so far
                "dag_head_width": head_width,      # tips at current head
                # Phase 24b: identifier of the current tip set (sha256 of
                # sorted tip hashes). Two nodes on the same DAG frontier
                # have identical frontier_root — useful for fast sync probe.
                "frontier_root": node.state.frontier_root().hex(),
                # Phase 24d: per-producer rate window (R-blocks-per-10s cap
                # + each producer's recent seal count). Operators can spot
                # producers near the cap and explain rejected-block events.
                "producer_rate_window": node.state.producer_rate_window(),
                # Phase 25a: opt-in QUIC gossip transport. Peers that find
                # this field in /info know to address us via QUIC for
                # block/tx fanout instead of HTTP. The pin = sha256(DER
                # subject_pubkey)[:16]; recipients can TOFU-pin it.
                "quic_cert_pin": node.quic_cert_pin if node.quic_enabled else None,
                "quic_enabled": bool(node.quic_enabled),
                # Phase 25c: HTTP /gossip/* removed. Always "quic-only"
                # in this code path; legacy nodes without --quic now
                # refuse to start with peers configured. Field exists so
                # peers can detect compatibility from /info alone.
                "gossip_transport": "quic-only",
            })

        if path == "/frontier":
            # Phase 24b §6: returns the canonical tip set as of an optional
            # height (defaults to current head). Lets a joining node ask
            # "what's the merge boundary you're working from?" before pulling
            # the full block payload set.
            qs = (dict(p.split("=",1) for p in self.path.split("?",1)[1].split("&") if "=" in p)
                  if "?" in self.path else {})
            height_arg = qs.get("height")
            c = node.state._conn()
            try:
                if height_arg is None:
                    row = c.execute("SELECT MAX(height) FROM blocks").fetchone()
                    h = (row[0] or 0)
                else:
                    h = int(height_arg)
                if h <= 0:
                    return self._json(200, {"height": 0, "tips": [],
                                            "frontier_root": node.state.frontier_root([]).hex()})
                rows = c.execute(
                    "SELECT hash FROM blocks WHERE height = ?", (h,)
                ).fetchall()
                tip_hashes = [bytes.fromhex(r[0]) for r in rows]
                return self._json(200, {
                    "height": h,
                    "tips": [t.hex() for t in tip_hashes],
                    "frontier_root": node.state.frontier_root(tip_hashes).hex(),
                })
            finally:
                c.close()

        if path == "/bootstrap":
            # Phase 19b: machine-readable bootstrap data for new nodes.
            # Returns peer URLs (this node + its known peers) and the chain's
            # treasury so a fresh node can register its producer + start.
            from . import FINALITY_DEPTH
            host_port = self.headers.get("Host", f"127.0.0.1:{self.server.server_port}")
            self_url = f"http://{host_port}"
            return self._json(200, {
                "self": self_url,
                "peers": [p for p in node.peers] + [self_url],
                "treasury": node.state.treasury,
                "finality_depth": FINALITY_DEPTH,
                "head_height": (node.state.latest_blocks(1) or [{"height":0}])[0]["height"],
                "registered_producers": len(node.state.list_producers()),
            })

        if path == "/tip":
            return self._json(200, {"tips": [h.hex() for h in node.state.tip_hashes()]})

        if path == "/blocks/latest":
            n = 10
            if "?" in self.path:
                qs = dict(p.split("=", 1) for p in self.path.split("?", 1)[1].split("&") if "=" in p)
                n = int(qs.get("n", 10))
            return self._json(200, {"blocks": node.state.latest_blocks(n)})

        m = re.match(r"^/block/([0-9a-f]+)$", path)
        if m:
            c = node.state._conn()
            row = c.execute("SELECT payload FROM blocks WHERE hash=?",
                             (m.group(1),)).fetchone()
            c.close()
            if not row:
                return self._json(404, {"error": "not found"})
            return self._json(200, json.loads(row[0]))

        m = re.match(r"^/blocks/at/(\d+)$", path)
        if m:
            h = int(m.group(1))
            c = node.state._conn()
            rows = c.execute("SELECT payload FROM blocks WHERE height=?",
                             (h,)).fetchall()
            c.close()
            return self._json(200, {"blocks": [json.loads(r[0]) for r in rows]})

        m = re.match(r"^/account/((?:m0r|0x)[0-9a-zA-Z]+)$", path)
        if m:
            return self._json(200, node.state.get_account(m.group(1)))

        m = re.match(r"^/content/(0x[0-9a-fA-F]+)$", path)
        if m:
            res = node.state.get_content(m.group(1))
            return self._json(200 if res else 404, res or {"error": "not found"})

        m = re.match(r"^/order/(0x[0-9a-fA-F]+)$", path)
        if m:
            res = node.state.get_order(m.group(1))
            return self._json(200 if res else 404, res or {"error": "not found"})

        m = re.match(r"^/job/(0x[0-9a-fA-F]+)$", path)
        if m:
            res = node.state.get_job(m.group(1))
            return self._json(200 if res else 404, res or {"error": "not found"})

        if path == "/ai-services":
            c = node.state._conn()
            try:
                rows = c.execute(
                    "SELECT pubkey, name, registered_at FROM ai_services "
                    "ORDER BY registered_at"
                ).fetchall()
                from . import crypto as _crypto
                out = []
                for pk, name, at in rows:
                    pk_bytes = bytes.fromhex(pk)
                    out.append({"pubkey": pk, "address": _crypto.address(pk_bytes),
                                "name": name, "registered_at": at})
                return self._json(200, {"services": out})
            finally:
                c.close()

        if path == "/jobs":
            qs = dict(p.split("=", 1) for p in self.path.split("?", 1)[-1].split("&") if "=" in p) if "?" in self.path else {}
            status = int(qs["status"]) if "status" in qs else None
            return self._json(200, {"jobs": node.state.list_jobs(status=status)})

        m = re.match(r"^/worker/((?:m0r|0x)[0-9a-zA-Z]+)$", path)
        if m:
            return self._json(200, node.state.get_worker_stats(m.group(1)))

        if path == "/bridge/burns":
            qs = (dict(p.split("=",1) for p in self.path.split("?",1)[1].split("&") if "=" in p)
                  if "?" in self.path else {})
            only_pending = qs.get("only_pending") == "1"
            c = node.state._conn()
            try:
                where = "WHERE evm_unlocked = 0" if only_pending else ""
                rows = c.execute(
                    f"SELECT burn_tx_hash, burner, amount, evm_recipient, "
                    f"token, token_address, evm_unlocked, burned_at "
                    f"FROM bridge_burns {where} ORDER BY burned_at"
                ).fetchall()
                keys = ["burn_tx_hash","burner","amount","evm_recipient",
                        "token","token_address","evm_unlocked","burned_at"]
                return self._json(200, {"burns": [dict(zip(keys, r)) for r in rows]})
            finally:
                c.close()

        m = re.match(r"^/views/(0x[0-9a-fA-F]+)$", path)
        if m:
            cid = m.group(1)
            c = node.state._conn()
            try:
                rows = c.execute(
                    "SELECT viewer, cell_index, rewarded_at FROM views "
                    "WHERE content_id=? ORDER BY rewarded_at",
                    (cid,),
                ).fetchall()
                return self._json(200, {
                    "content_id": cid,
                    "view_count": len(rows),
                    "viewers": [{"viewer": r[0], "cell_index": r[1],
                                  "at": r[2]} for r in rows],
                })
            finally:
                c.close()

        self._json(404, {"error": "not found"})

    def do_POST(self):
        path = self.path.split("?", 1)[0]
        node: Node = self.server.node
        if path == "/tx":
            try:
                body = self._read_json()
                tx = Transaction.from_dict(body)
            except Exception as e:
                return self._json(400, {"error": f"bad tx: {e}"})
            ok = node.submit_tx(tx)
            # Phase 26c: clients want to distinguish "bad signature/nonce"
            # from "DoS cap reached". The submit_tx return value is just a
            # bool, so we infer the reason from the resulting state: if the
            # tx wasn't queued AND the queue is at capacity OR the sender
            # is at quota, label it as a cap rejection.
            resp = {"ok": ok, "tx_hash": tx.hash().hex(),
                    "mempool_size": len(node.mempool)}
            if not ok:
                if len(node.mempool) >= node.mempool_max_txs:
                    resp["error"] = "mempool full"
                    resp["limit"] = node.mempool_max_txs
                elif node._sender_count.get(tx.sender, 0) >= node.mempool_max_per_sender:
                    resp["error"] = "per-sender quota exceeded"
                    resp["limit"] = node.mempool_max_per_sender
                else:
                    resp["error"] = "tx invalid (signature/nonce)"
            return self._json(200 if ok else 400, resp)

        # Phase 25c (2026-04-26): HTTP /gossip/tx + /gossip/block removed.
        # Gossip is now QUIC-only — every node must run with --quic and
        # advertise quic_cert_pin in /info. The 410 status quickly tells
        # any old-version peer "this endpoint is gone, upgrade".
        if path in ("/gossip/tx", "/gossip/block"):
            return self._json(410, {
                "error": "HTTP gossip removed in Phase 25c; "
                         "node must speak QUIC (see /info.quic_cert_pin)",
                "removed_in": "Phase 25c",
            })

        if path == "/bridge/burn-confirmed":
            # relayer-only: marks a burn as having been unlocked on EVM. This
            # is purely an off-chain bookkeeping flag; doesn't change balances.
            body = self._read_json()
            burn_hash = body.get("burn_tx_hash")
            if not burn_hash:
                return self._json(400, {"error": "missing burn_tx_hash"})
            c = node.state._conn()
            try:
                row = c.execute(
                    "UPDATE bridge_burns SET evm_unlocked = 1 WHERE burn_tx_hash = ?",
                    (burn_hash,),
                )
                c.execute("COMMIT") if False else None
                return self._json(200, {"ok": True, "burn_tx_hash": burn_hash})
            finally:
                c.close()

        if path == "/credit":
            # ⚠ DEV/SINGLE-NODE ONLY — bypasses gossip → causes state divergence
            # across peers. For multi-node, use a TRANSFER tx signed by treasury.
            if node.peers:
                return self._json(403, {
                    "error": "/credit is single-node only; this node has peers — "
                             "use a TRANSFER tx instead"})
            body = self._read_json()
            recipient = body["to"]
            amount = int(body["amount"])
            c = node.state._conn()
            try:
                c.execute("BEGIN IMMEDIATE")
                row = c.execute("SELECT balance FROM accounts WHERE address=?",
                                (node.state.treasury,)).fetchone()
                if not row or row[0] < amount:
                    c.execute("ROLLBACK")
                    return self._json(400, {"error": "treasury insufficient"})
                c.execute("UPDATE accounts SET balance=balance-? WHERE address=?",
                          (amount, node.state.treasury))
                node.state._ensure_account(c, recipient)
                c.execute("UPDATE accounts SET balance=balance+? WHERE address=?",
                          (amount, recipient))
                c.execute("COMMIT")
                return self._json(200, {"ok": True, "to": recipient, "amount": amount})
            except Exception as e:
                c.execute("ROLLBACK")
                return self._json(400, {"error": str(e)})
            finally:
                c.close()

        self._json(404, {"error": "not found"})


class RpcServer(ThreadingHTTPServer):
    allow_reuse_address = True

    # Skip the reverse-DNS lookup that http.server.HTTPServer.server_bind
    # does via socket.getfqdn(). On macOS hosts whose mDNSResponder is slow
    # or misconfigured (observed: Mac Mini "mini.local" Tahoe — 35 s hang
    # before bind returns), the unresolved getfqdn blocks the entire RPC
    # listener startup. We don't actually need server_name anywhere.
    def server_bind(self):
        from socketserver import TCPServer
        TCPServer.server_bind(self)
        host, port = self.server_address[:2]
        self.server_name = host        # use the literal — no DNS lookup
        self.server_port = port
