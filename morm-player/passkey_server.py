"""Passkey gateway HTTP server (separate process from edge nodes).

Lives at http://127.0.0.1:8800 by default. Wraps:
  - WebAuthn registration/authentication (auth.py)
  - eth tx broadcasting via the user's custodial key (web3.py + anvil)

Endpoints
  GET  /                          → /static/auth.html
  GET  /static/*                  → static assets
  POST /api/auth/begin-register   → WebAuthn registration options
  POST /api/auth/finish-register  → verify + create custodial ETH account
  POST /api/auth/begin-auth       → WebAuthn assertion options
  POST /api/auth/finish-auth      → verify, return public passkey info
  POST /api/auth/sign-and-send    → verify + broadcast a tx with the user's key
  GET  /api/auth/list             → list registered passkeys
  GET  /api/escrow/info           → exported escrow contract address + abi
"""
from __future__ import annotations

import argparse
import json
import mimetypes
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from eth_account import Account
from web3 import Web3

import auth as authmod

ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "static"


class Handler(BaseHTTPRequestHandler):
    server_version = "MORMPasskey/0.1"

    def log_message(self, fmt, *args):
        sys.stderr.write(f"[passkey] {fmt % args}\n")

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self):
        self.send_response(204); self._cors(); self.end_headers()

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path in ("/", "/auth", "/auth.html"):
            return self._serve_static("auth.html")
        if path.startswith("/static/"):
            return self._serve_static(path[len("/static/"):])
        if path == "/api/auth/list":
            return self._json(200, {"passkeys": self.server.store.list_passkeys()})
        if path == "/api/escrow/info":
            return self._json(200, {
                "escrow": self.server.escrow_address,
                "rpc": self.server.rpc_url,
                "chain_id": self.server.chain_id,
            })
        return self._not_found()

    def do_POST(self):
        path = self.path.split("?", 1)[0]
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        body = self.rfile.read(length) if length else b""
        try:
            payload = json.loads(body) if body else {}
        except json.JSONDecodeError:
            return self._json(400, {"error": "invalid json"})

        if path == "/api/auth/begin-register":
            opts = authmod.begin_register(self.server.store,
                                          self.server.rp_id, self.server.origin,
                                          user_name=payload.get("user_name"))
            return self._raw(200, opts, "application/json")

        if path == "/api/auth/finish-register":
            try:
                result = authmod.finish_register(self.server.store,
                                                 self.server.rp_id, self.server.origin,
                                                 payload)
            except Exception as e:
                return self._json(400, {"ok": False, "error": str(e)})
            if result.get("ok") and self.server.fund_amount > 0:
                self._fund(result["eth_address"])
            return self._json(200 if result.get("ok") else 400, result)

        if path == "/api/auth/begin-auth":
            opts = authmod.begin_auth(self.server.store,
                                      self.server.rp_id, self.server.origin,
                                      payload.get("credential_id"))
            return self._raw(200, opts, "application/json")

        if path == "/api/auth/finish-auth":
            # Returns the server's key share. Browser combines it with its own
            # IndexedDB share to reconstruct the privkey *locally*, signs, and
            # broadcasts via /api/relay/raw-tx. The server cannot sign alone.
            try:
                result = authmod.finish_auth(self.server.store,
                                              self.server.rp_id, self.server.origin,
                                              payload)
            except Exception as e:
                return self._json(400, {"ok": False, "error": str(e)})
            return self._json(200 if result.get("ok") else 400, result)

        if path == "/api/relay/raw-tx":
            return self._relay_raw_tx(payload)
        if path == "/api/dev/register" and self.server.dev_mode:
            return self._dev_register(payload)
        if path == "/api/dev/share" and self.server.dev_mode:
            return self._dev_share(payload)

        return self._not_found()

    def _dev_register(self, payload):
        """DEV-ONLY: skip WebAuthn, simulate a passkey-bound account with split key."""
        import base64, secrets as _secrets
        cred_id = _secrets.token_bytes(16)
        user_handle = _secrets.token_urlsafe(16)
        acct = Account.create()
        privkey = bytes.fromhex(acct.key.hex().removeprefix("0x"))
        server_share = _secrets.token_bytes(32)
        client_share = bytes(a ^ b for a, b in zip(privkey, server_share))
        self.server.store.save_passkey(
            credential_id=cred_id, user_handle=user_handle,
            public_key=b"DEV-MODE-NO-PUBKEY", sign_count=0,
            eth_address=acct.address, server_share_hex=server_share.hex(),
        )
        if self.server.fund_amount > 0:
            self._fund(acct.address)
        del privkey
        return self._json(200, {
            "ok": True,
            "credential_id": base64.urlsafe_b64encode(cred_id).decode().rstrip("="),
            "eth_address": acct.address,
            "user_handle": user_handle,
            "client_share": client_share.hex(),
            "dev_mode": True,
        })

    def _dev_share(self, payload):
        """DEV-ONLY: hand back the server share without WebAuthn (testing only)."""
        import base64
        cid_b64 = payload["credential_id"]
        cid = base64.urlsafe_b64decode(cid_b64 + "=" * (-len(cid_b64) % 4))
        saved = self.server.store.get_passkey(cid)
        if not saved:
            return self._json(404, {"ok": False, "error": "unknown credential"})
        return self._json(200, {
            "ok": True,
            "eth_address": saved["eth_address"],
            "server_share": saved["server_share"],
        })

    def _relay_raw_tx(self, payload):
        """Broadcast a browser-signed raw transaction to anvil. The server
        only relays; it cannot construct or sign the tx itself."""
        raw_hex = payload.get("raw_tx")
        if not raw_hex:
            return self._json(400, {"ok": False, "error": "missing raw_tx"})
        w3 = self.server.w3
        try:
            tx_hash = w3.eth.send_raw_transaction(bytes.fromhex(raw_hex.removeprefix("0x")))
        except Exception as e:
            return self._json(400, {"ok": False, "error": f"broadcast: {e}"})
        try:
            receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=10)
        except Exception as e:
            return self._json(200, {"ok": True, "tx_hash": tx_hash.hex(), "receipt": None,
                                     "warning": str(e)})
        return self._json(200, {
            "ok": True,
            "tx_hash": tx_hash.hex(),
            "block": receipt.blockNumber,
            "status": receipt.status,
        })

    def _fund(self, address: str):
        """Send a bit of anvil-default ETH to the new passkey account so it can pay gas."""
        w3 = self.server.w3
        if not w3.is_connected():
            return
        deployer_key = self.server.deployer_key
        deployer = Account.from_key(deployer_key)
        nonce = w3.eth.get_transaction_count(deployer.address)
        tx = {
            "from": deployer.address, "to": Web3.to_checksum_address(address),
            "value": self.server.fund_amount,
            "nonce": nonce, "gas": 21000, "gasPrice": w3.eth.gas_price,
            "chainId": self.server.chain_id,
        }
        signed = w3.eth.account.sign_transaction(tx, private_key=deployer_key)
        w3.eth.send_raw_transaction(signed.raw_transaction)

    # ----- helpers -----

    def _serve_static(self, name: str):
        target = (STATIC / name).resolve()
        if not str(target).startswith(str(STATIC)) or not target.is_file():
            return self._not_found()
        mime = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        body = target.read_bytes()
        self.send_response(200); self._cors()
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers(); self.wfile.write(body)

    def _json(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(status); self._cors()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers(); self.wfile.write(body)

    def _raw(self, status, body: bytes, mime: str):
        self.send_response(status); self._cors()
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers(); self.wfile.write(body)

    def _not_found(self):
        self.send_response(404); self._cors(); self.end_headers()
        self.wfile.write(b"not found\n")


class PasskeyServer(ThreadingHTTPServer):
    allow_reuse_address = True


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8800)
    p.add_argument("--db", default=str(ROOT / "passkeys.db"))
    p.add_argument("--rp-id", default="localhost")
    p.add_argument("--origin", default="http://localhost:8800")
    p.add_argument("--rpc-url", default="http://127.0.0.1:8545")
    p.add_argument("--chain-id", type=int, default=31337)
    p.add_argument("--escrow",
                   default="0x5FbDB2315678afecb367f032d93F642f64180aa3")
    p.add_argument("--deployer-key",
                   default="0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80")
    p.add_argument("--fund-eth", type=float, default=0.1,
                   help="ETH to forward to new passkey accounts (0 = none)")
    p.add_argument("--dev-mode", action="store_true",
                   help="enable /api/dev/* endpoints that bypass WebAuthn (testing only)")
    args = p.parse_args(argv)

    httpd = PasskeyServer((args.host, args.port), Handler)
    httpd.store = authmod.AuthStore(Path(args.db))
    httpd.rp_id = args.rp_id
    httpd.origin = args.origin
    httpd.rpc_url = args.rpc_url
    httpd.chain_id = args.chain_id
    httpd.escrow_address = Web3.to_checksum_address(args.escrow)
    httpd.deployer_key = args.deployer_key
    httpd.w3 = Web3(Web3.HTTPProvider(args.rpc_url))
    httpd.fund_amount = int(args.fund_eth * 1e18)
    httpd.dev_mode = args.dev_mode
    if args.dev_mode:
        print("           ⚠️  DEV MODE — /api/dev/* endpoints exposed (bypasses WebAuthn)")

    print(f"[passkey] listening on http://{args.host}:{args.port}/  rp_id={args.rp_id}  origin={args.origin}")
    print(f"          rpc={args.rpc_url}  escrow={httpd.escrow_address}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    os.chdir(ROOT)
    raise SystemExit(main())
