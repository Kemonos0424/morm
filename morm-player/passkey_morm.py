"""Passkey gateway for the *MORM Chain* L1 (Phase 10e + 11b).

Differences from passkey_server.py:
  - keys are ed25519, not secp256k1
  - tx format is MORM Chain (Transaction.to_dict()), not Ethereum legacy
  - relay endpoint POSTs to MORM L1 /tx, not anvil
  - WebAuthn ceremony + 2-of-2 XOR key split are unchanged
  - serves auth-morm.html / auth-morm.js for the in-browser flow

Same surface for the browser: register passkey → store client_share, sign-in
→ receive server_share → reconstruct privkey locally → sign Tx → relay.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import mimetypes
import os
import re
import secrets
import subprocess
import sys
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "static"

# pull in MORM L1 + auth helpers
sys.path.insert(0, str(ROOT.parent / "morm-l1"))
from morm_l1 import crypto as l1crypto  # noqa: E402

import auth as authmod  # noqa: E402
import jobs as jobsmod  # noqa: E402
import storage as storagemod  # noqa: E402


def split_key(seed: bytes) -> tuple[bytes, bytes]:
    """Return (server_share, client_share) such that XOR == seed."""
    server = secrets.token_bytes(32)
    client = bytes(a ^ b for a, b in zip(seed, server))
    return server, client


# Phase 26y — Service Worker version probe.
# The SW fetches GET /sw-version on activate; when the value changes it
# purges its caches before serving any request, bounding the lifetime of
# stale code on the client. The hash covers sw.js plus every shell asset
# under static/, so any source change triggers an upstream version bump
# even when sw.js itself wasn't edited.
_SW_VERSION_CACHE: str | None = None
def _shell_bundle_version() -> str:
    global _SW_VERSION_CACHE
    if _SW_VERSION_CACHE is not None:
        return _SW_VERSION_CACHE
    h = hashlib.sha256()
    files = [STATIC / "sw.js"]
    for sub in sorted(STATIC.rglob("*")):
        if sub.is_file() and sub != (STATIC / "sw.js"):
            files.append(sub)
    for f in files:
        rel = f.relative_to(STATIC).as_posix()
        h.update(rel.encode())
        h.update(b"\0")
        h.update(f.read_bytes())
        h.update(b"\0")
    _SW_VERSION_CACHE = h.hexdigest()[:16]
    return _SW_VERSION_CACHE


def _rewrite_m3u8(text: str, *, cdn_base: str, content_id: str,
                  rel_dir: str) -> str:
    """Phase 25Vc: rewrite relative URIs in a HLS playlist so they point at
    the CDN. Two file types:
      - master.m3u8 (rel_dir == ""): refers to sub-playlists like
        "1080p/index.m3u8" — these become
        "<cdn>/api/video/<cid>/1080p/index.m3u8".
      - sub-playlist <res>/index.m3u8 (rel_dir == "<res>"): refers to
        init_*.mp4 (in EXT-X-MAP:URI) and seg_*.m4s lines — both get the
        same rewrite under "<cdn>/api/video/<cid>/<res>/...".
    Lines we don't touch: empty lines, comments other than EXT-X-MAP, and
    anything that already starts with http:// or https://.
    """
    base = cdn_base.rstrip("/")
    prefix = f"{base}/api/video/{content_id}"
    out_lines = []
    for line in text.splitlines():
        s = line.strip()
        if not s:
            out_lines.append(line); continue
        # EXT-X-MAP:URI="init_X.mp4"  → rewrite the URI value in place
        if s.startswith("#EXT-X-MAP:") and 'URI="' in s:
            head, _, rest = s.partition('URI="')
            uri, _, tail = rest.partition('"')
            if uri.startswith(("http://", "https://")):
                out_lines.append(line); continue
            sub = uri if not rel_dir else f"{rel_dir}/{uri}"
            out_lines.append(f'{head}URI="{prefix}/{sub}"{tail}')
            continue
        if s.startswith("#"):
            out_lines.append(line); continue
        if s.startswith(("http://", "https://")):
            out_lines.append(line); continue
        # bare segment / sub-playlist URI line
        sub = s if not rel_dir else f"{rel_dir}/{s}"
        out_lines.append(f"{prefix}/{sub}")
    return "\n".join(out_lines) + ("\n" if text.endswith("\n") else "")


class Handler(BaseHTTPRequestHandler):
    server_version = "MORMPasskeyL1/0.1"

    def log_message(self, fmt, *args):
        sys.stderr.write(f"[passkey-morm] {fmt % args}\n")

    # Phase 26v: which origin to advertise in Access-Control-Allow-Origin.
    # When `--allowed-origins` is unset, we keep the legacy "*" (compatible
    # with curl, dev tooling, and any browser caller). When set, we echo
    # back ONLY the request's Origin if it matches the allowlist; otherwise
    # we send no Access-Control-Allow-Origin (browser CORS-blocks the
    # response). Echoing the matched origin (rather than "*") is mandatory
    # whenever `Access-Control-Allow-Credentials: true` is set; we don't
    # use credentials yet but follow the same pattern for consistency.
    def _allowed_origins(self) -> set | None:
        return getattr(self.server, "allowed_origins", None)

    def _origin_matched(self) -> str | None:
        """Return the request's Origin header iff it is in the allowlist,
        else None. With no allowlist (legacy mode) returns "*"."""
        allow = self._allowed_origins()
        if not allow:
            return "*"
        origin = self.headers.get("Origin", "")
        return origin if origin in allow else None

    def _cors(self):
        ao = self._origin_matched()
        if ao:
            self.send_header("Access-Control-Allow-Origin", ao)
            if ao != "*":
                # When echoing an explicit origin we must vary on it so
                # caches don't pin the wrong origin into a response.
                self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _check_csrf_or_reject(self) -> bool:
        """Phase 26u: for state-changing endpoints, require Origin to match
        the configured allowlist when one is set. Returns True if the
        request is allowed to proceed; False after sending a 403 response.

        Browser-issued POST requests always include an Origin header (per
        the Fetch spec), so a missing Origin in strict mode is a strong
        signal of a non-browser caller (or a CSRF probe stripping it).
        Same-origin browser requests pass naturally because the gateway
        is itself one of the allowed origins."""
        allow = self._allowed_origins()
        if not allow:
            return True   # legacy mode: no CSRF protection (logged elsewhere)
        origin = self.headers.get("Origin", "")
        if origin and origin in allow:
            return True
        sys.stderr.write(
            f"[csrf] reject POST {self.path!r}: Origin={origin!r} "
            f"not in allowlist {sorted(allow)}\n"
        )
        self._json(403, {
            "error": "Origin not allowed (Phase 26u CSRF protection)",
            "origin": origin,
            "hint": "this gateway only accepts cross-origin POSTs from "
                    "configured --allowed-origins",
        })
        return False

    def do_OPTIONS(self):
        self.send_response(204); self._cors(); self.end_headers()

    def _json(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(status); self._cors()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers(); self.wfile.write(body)

    def _read_json(self):
        n = int(self.headers.get("Content-Length", "0") or 0)
        return json.loads(self.rfile.read(n).decode()) if n else {}

    def _serve_static(self, name: str):
        target = (STATIC / name).resolve()
        if not str(target).startswith(str(STATIC)) or not target.is_file():
            return self._json(404, {"error": "not found"})
        mime = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        body = target.read_bytes()
        self.send_response(200); self._cors()
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers(); self.wfile.write(body)

    # ---- Phase 25Va: HLS asset serving ---------------------------------
    # Content-Type and Cache-Control follow PHASE25-VIDEO.md §4. Media
    # segments and init.mp4 are content-addressed (filename embeds the
    # SHA256 prefix), so they are immutable and can be cached for a year.
    # The .m3u8 playlists may be re-encoded so they get a short TTL.
    _HLS_MIME = {
        ".m3u8": "application/vnd.apple.mpegurl",
        ".m4s":  "video/iso.segment",
        ".mp4":  "video/mp4",
        ".json": "application/json; charset=utf-8",
    }
    _HLS_CACHE_LONG  = "public, max-age=31536000, immutable"
    _HLS_CACHE_SHORT = "public, max-age=300"

    def _serve_hls(self, content_id: str, rel: str):
        root = getattr(self.server, "hls_storage_dir", None)
        if not root:
            return self._json(404, {"error": "HLS storage not configured"})
        # Resolve under <storage>/<content_id>/<rel>; reject any path
        # traversal that escapes the per-content directory.
        base = (root / content_id).resolve()
        if not base.exists() or not base.is_dir():
            return self._json(404, {"error": "content not found"})
        target = (base / rel).resolve()
        if not str(target).startswith(str(base) + "/") and target != base:
            return self._json(403, {"error": "path traversal"})
        if not target.is_file():
            return self._json(404, {"error": "not found"})

        ext = target.suffix.lower()
        mime = self._HLS_MIME.get(ext, "application/octet-stream")
        # init.mp4 / .m4s are immutable; .m3u8 short TTL; manifest.json no-store
        if ext in (".m4s", ".mp4"):
            cache = self._HLS_CACHE_LONG
        elif ext == ".m3u8":
            cache = self._HLS_CACHE_SHORT
        else:
            cache = "no-store"

        # Phase 25Vc: when --cdn-base-url is configured, rewrite playlists
        # so segment URIs point at the CDN. Origin still serves both
        # playlists and segments unchanged (3原則: CDN は加速層であり、
        # origin-only でも完全動作する保証); the rewrite happens
        # response-side so we don't have to duplicate playlist files.
        cdn = getattr(self.server, "cdn_base_url", None)
        if ext == ".m3u8" and cdn:
            body = _rewrite_m3u8(
                target.read_text(encoding="utf-8"),
                cdn_base=cdn,
                content_id=content_id,
                rel_dir=rel.rsplit("/", 1)[0] if "/" in rel else "",
            ).encode("utf-8")
            self.send_response(200); self._cors()
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", cache)
            self.send_header("X-MORM-CDN-Rewrite", "on")
            self.end_headers()
            self.wfile.write(body)
            return

        size = target.stat().st_size
        rng = self.headers.get("Range")
        start, end = 0, size - 1
        partial = False
        if rng:
            m = re.match(r"bytes=(\d*)-(\d*)", rng)
            if m:
                s, e = m.group(1), m.group(2)
                if s:
                    start = int(s)
                if e:
                    end = min(int(e), size - 1)
                partial = True
        length = end - start + 1
        self.send_response(206 if partial else 200); self._cors()
        self.send_header("Content-Type", mime)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(length))
        self.send_header("Cache-Control", cache)
        if partial:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.end_headers()
        with target.open("rb") as f:
            f.seek(start)
            remaining = length
            while remaining > 0:
                chunk = f.read(min(64 * 1024, remaining))
                if not chunk:
                    break
                try:
                    self.wfile.write(chunk)
                except (BrokenPipeError, ConnectionResetError):
                    return
                remaining -= len(chunk)

    # Phase 26r/s — gate any /api/signal/* request through the per-IP
    # token bucket. 429 is the canonical rate-limit status; clients see
    # `{error, retry_after}` and can back off accordingly.
    def _signal_rate_guard(self, path: str) -> bool:
        if not path.startswith("/api/signal/"):
            return True
        ip = self.client_address[0] if self.client_address else ""
        if self.server.sig_rate_take(ip):
            return True
        retry = max(1, int(1.0 / max(0.1, self.server.signal_rate_per_ip)))
        self.send_response(429); self._cors()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Retry-After", str(retry))
        body = json.dumps({"error": "signaling rate limit",
                           "retry_after": retry,
                           "rate_per_ip": self.server.signal_rate_per_ip}).encode()
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
        return False

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if not self._signal_rate_guard(path):
            return
        if path in ("/", "/auth-morm", "/auth-morm.html"):
            return self._serve_static("auth-morm.html")
        if path in ("/shop", "/shop.html"):
            return self._serve_static("shop.html")
        if path in ("/admin", "/admin.html"):
            return self._serve_static("admin.html")
        # Phase 25Va: HLS player served same-origin so its IndexedDB sees
        # the identity the gateway stored (VIEW_REWARD signing path).
        if path in ("/player-hls", "/player-hls.html"):
            return self._serve_static("player-hls.html")
        # Phase 25Vb: upload UI (multipart-ish: raw body + ?filename=...)
        if path in ("/upload", "/upload.html"):
            return self._serve_static("upload.html")
        # Phase 27g/h/i: wallet policy manager (per-app caps, kind
        # whitelist, 1-tap revoke). Same-origin so its localStorage
        # reads/writes the policy state every other MORM page enforces.
        if path in ("/wallet", "/wallet.html"):
            return self._serve_static("wallet.html")
        # Phase 28a: EVM ↔ MORM bridge UI. Two-tab page: "Lock" (MetaMask
        # signs an EVM lock(bytes20) → relayer mints µMORM) and "Burn"
        # (passkey-signed BRIDGE_BURN → relayer calls EVM unlock()). Bridge
        # contract / EVM RPC are surfaced via /api/morm/bridge so the JS
        # doesn't need a hardcoded address.
        if path in ("/swap", "/swap.html"):
            return self._serve_static("swap.html")
        # PWA shell — served from root for proper scope
        if path == "/manifest.webmanifest":
            return self._serve_static("manifest.webmanifest")
        if path == "/sw.js":
            # SW must be served at the root scope, not /static/, otherwise its
            # control is limited. Caching headers must allow updates.
            return self._serve_static("sw.js")
        # Phase 26y — version probe for the Service Worker. The SW fetches
        # this on activate (and periodically on subsequent app loads); when
        # the returned version differs from the one it cached on its prior
        # activate, the SW purges its shell+cells caches before serving any
        # request. This bounds the lifetime of stale buggy code without
        # waiting for the browser's own SW update cycle.
        if path == "/sw-version":
            return self._json(200, {"version": _shell_bundle_version()})
        if path in ("/player", "/index.html"):
            # serve the swarm player from the same origin as the gateway,
            # so its IndexedDB sees the identity the gateway just stored.
            return self._serve_static("index.html")
        if path.startswith("/static/"):
            return self._serve_static(path[len("/static/"):])

        # Phase 25Va: HLS video endpoints
        # /api/video/<cid>/master.m3u8
        # /api/video/<cid>/<resolution>/<filename>
        # /api/video/<cid>/manifest.json   (MORM-extension manifest)
        m = re.match(
            r"^/api/video/([0-9a-f]+)/(master\.m3u8|manifest\.json)$", path)
        if m:
            return self._serve_hls(m.group(1), m.group(2))
        m = re.match(
            r"^/api/video/([0-9a-f]+)/([0-9a-zA-Z_]+)/([\w.\-]+)$", path)
        if m:
            return self._serve_hls(m.group(1), f"{m.group(2)}/{m.group(3)}")
        m = re.match(r"^/api/video/list$", path)
        if m:
            return self._json(200, {"contents": self.server.list_hls_contents()})
        # Phase 25Vb: job status polling
        m = re.match(r"^/api/video/job/([0-9a-f]+)$", path)
        if m:
            st = self.server.jobs.get(m.group(1)) if self.server.jobs else None
            if not st:
                return self._json(404, {"error": "job not found"})
            return self._json(200, st.to_dict())
        if path == "/api/video/jobs":
            jobs = (self.server.jobs.list_recent(20)
                    if self.server.jobs else [])
            return self._json(200, {"jobs": [j.to_dict() for j in jobs]})
        if path == "/api/auth/list":
            return self._json(200, {"passkeys": self.server.store.list_passkeys()})

        # Phase 22: signaling
        m = re.match(r"^/api/signal/peers/([0-9a-fA-F]+)$", path)
        if m:
            cid = m.group(1)
            qs = (dict(p.split("=", 1) for p in self.path.split("?", 1)[1].split("&")
                       if "=" in p) if "?" in self.path else {})
            exclude = qs.get("exclude")
            return self._json(200, {"peers": self.server.sig_peers_for(cid, exclude)})

        m = re.match(r"^/api/signal/inbox/([0-9a-fA-F]+)$", path)
        if m:
            return self._json(200, {"messages": self.server.sig_inbox(m.group(1))})
        if path == "/api/signal/ice":
            from urllib.parse import parse_qs, urlparse
            q = parse_qs(urlparse(self.path).query)
            peer_id = (q.get("peer_id") or [""])[0]
            return self._json(200, {"ice_servers": self.server.ice_servers_for(peer_id)})
        if path == "/api/morm/info":
            try:
                with urllib.request.urlopen(
                    self.server.morm_rpc.rstrip("/") + "/info", timeout=2,
                ) as r:
                    info = json.loads(r.read())
                return self._json(200, {
                    "rpc": self.server.morm_rpc,
                    "treasury": info.get("treasury"),
                    "state_root": info.get("state_root"),
                    "cdn_base_url": getattr(self.server, "cdn_base_url", None),
                })
            except Exception as e:
                return self._json(502, {"ok": False, "error": str(e)})
        # Phase 28a/28b: bridge config for /swap. Returns the deployed
        # MORMBridge address + EVM RPC so the page can construct a
        # web3 contract handle without hardcoded values. ERC-20
        # (USDC) bridge is optional — the JS unhides the USDC tab
        # only when both `erc20_bridge_addr` and `usdc_addr` are set.
        if path == "/api/morm/bridge":
            return self._json(200, {
                "bridge_addr":       getattr(self.server, "bridge_addr", None),
                "evm_rpc":           getattr(self.server, "evm_rpc_url", None),
                "evm_chain_id":      getattr(self.server, "evm_chain_id", None),
                "erc20_bridge_addr": getattr(self.server, "erc20_bridge_addr", None),
                "usdc_addr":         getattr(self.server, "usdc_addr", None),
            })
        return self._json(404, {"error": "not found"})

    def do_POST(self):
        path = self.path.split("?", 1)[0]
        # Phase 26r/s — rate-limit signaling endpoints first so a flooded
        # gateway doesn't even bother parsing JSON body / checking CSRF
        # for already-rejected IPs.
        if not self._signal_rate_guard(path):
            return
        # Phase 26u: CSRF protection. Every POST is state-changing in this
        # gateway (relay tx, treasury actions, signaling); reject any
        # request whose Origin isn't in the allowlist. In legacy mode
        # (`--allowed-origins` unset) this is a no-op for compatibility.
        if not self._check_csrf_or_reject():
            return
        # POST /api/evidence/upload is binary; route before the JSON parser
        if path == "/api/evidence/upload":
            return self._handle_evidence_upload()
        # Phase 25Vb: video upload is binary; same pre-JSON pattern
        if path == "/api/video/upload":
            return self._handle_video_upload()
        try:
            payload = self._read_json()
        except json.JSONDecodeError:
            return self._json(400, {"error": "bad json"})

        if path == "/api/dev/register" and self.server.dev_mode:
            return self._dev_register(payload)
        if path == "/api/dev/share" and self.server.dev_mode:
            return self._dev_share(payload)
        if path == "/api/relay/morm-tx":
            return self._relay_morm_tx(payload)
        if path == "/api/treasury/credit":
            return self._treasury_credit(payload)
        if path == "/api/treasury/finalize":
            return self._treasury_finalize(payload)

        # Phase 22 signaling — POST endpoints
        if path == "/api/signal/announce":
            self.server.sig_announce(
                payload["peer_id"], payload["content_id"],
                payload.get("cells", []),
            )
            return self._json(200, {"ok": True})
        if path == "/api/signal/send":
            self.server.sig_send(payload["to"], {
                "from": payload["from"], "kind": payload["kind"],
                "data": payload.get("data"),
            })
            return self._json(200, {"ok": True})
        # /api/evidence/upload is multipart-ish; handled separately
        return self._json(404, {"error": "not found"})

    def do_PUT(self):
        # alias: PUT /api/evidence/upload?role=packing&order_id=0x...
        return self._handle_evidence_upload()

    # ---- Phase 25Vb: HLS upload pipeline -------------------------------
    def _handle_video_upload(self):
        """Receive a raw video Blob (the entire request body) under
        /api/video/upload?filename=<name>. Drops it on disk, enqueues a
        background hls-encode job, returns the job_id immediately.

        We deliberately skip multipart/form-data parsing — the browser side
        sets Content-Type: video/* and POSTs File.arrayBuffer() directly,
        which keeps the server flat and avoids a multipart parser dep
        (mirrors the existing /api/evidence/upload pattern)."""
        from urllib.parse import parse_qs, urlparse
        if not self.server.jobs or not self.server.upload_storage:
            return self._json(503, {
                "error": "uploads disabled",
                "hint": "start with --hls-storage-dir to enable",
            })
        q = parse_qs(urlparse(self.path).query)
        fname = (q.get("filename") or ["upload.mp4"])[0]
        # restrict to a known set of containers; the encoder runs ffmpeg
        # which can probe many formats but we keep the surface small
        allowed_ext = {".mp4", ".mov", ".webm", ".mkv", ".m4v"}
        ext = ("." + fname.rsplit(".", 1)[-1].lower()) if "." in fname else ""
        if ext not in allowed_ext:
            return self._json(400, {
                "error": f"extension {ext or '(none)'} not allowed",
                "allowed": sorted(allowed_ext),
            })

        n = int(self.headers.get("Content-Length", "0") or 0)
        max_n = self.server.max_upload_bytes
        if n == 0:
            return self._json(400, {"error": "empty body"})
        if n > max_n:
            return self._json(413, {
                "error": f"oversize body ({n} > {max_n})",
            })

        upload_dir = Path("/tmp/morm-25vb-uploads")
        upload_dir.mkdir(parents=True, exist_ok=True)
        # avoid collisions across simultaneous uploads
        tmp_path = upload_dir / f"upload-{secrets.token_hex(6)}{ext}"
        # stream from socket to disk to avoid pinning N MB in memory
        remaining = n
        with tmp_path.open("wb") as f:
            while remaining > 0:
                chunk = self.rfile.read(min(64 * 1024, remaining))
                if not chunk:
                    break
                f.write(chunk)
                remaining -= len(chunk)
        actual = tmp_path.stat().st_size
        if actual != n:
            tmp_path.unlink(missing_ok=True)
            return self._json(400, {
                "error": f"short read: expected {n} got {actual}",
            })

        st = self.server.jobs.submit_encode(
            src_path=tmp_path,
            out_root=self.server.upload_storage.root,    # FS backend only for now
            morm_core_python=self.server.morm_core_python,
            morm_core_dir=Path(self.server.morm_core_dir),
            bytes_in=actual,
        )
        return self._json(200, {"ok": True, **st.to_dict()})

    def _handle_evidence_upload(self):
        """Receive a raw video Blob (the body), drop it on disk under
        evidence/<role>-<order-id>/source.webm, then call morm-core's
        evidence encoder with the latest MORM L1 block hash. The returned
        proof_hash is what the browser uses for submitProof()."""
        from urllib.parse import parse_qs, urlparse
        q = parse_qs(urlparse(self.path).query)
        role     = (q.get("role")     or [""])[0]
        order_id = (q.get("order_id") or [""])[0]
        if role not in ("packing", "opening"):
            return self._json(400, {"error": "role must be packing|opening"})
        if not (order_id.startswith("0x") and len(order_id) == 66):
            return self._json(400, {"error": "order_id must be 0x + 64 hex"})

        n = int(self.headers.get("Content-Length", "0") or 0)
        if n == 0 or n > 50 * 1024 * 1024:
            return self._json(400, {"error": "empty or oversize body (max 50MB)"})
        body = self.rfile.read(n)

        evidence_dir = Path("/tmp/morm-camera-evidence") / f"{role}-{order_id[2:14]}"
        evidence_dir.mkdir(parents=True, exist_ok=True)
        src = evidence_dir / "source.webm"
        src.write_bytes(body)

        try:
            # latest MORM L1 block hash for the watermark
            with urllib.request.urlopen(self.server.morm_rpc.rstrip("/") + "/info",
                                         timeout=2) as r:
                info = json.loads(r.read())
            latest = info.get("latest") or []
            if latest:
                block_hash = "0x" + latest[0]["hash"]
            else:
                block_hash = "0x" + info["tips"][0]
        except Exception as e:
            return self._json(502, {"error": f"morm rpc: {e}"})

        out_dir = evidence_dir / "encoded"
        # call morm-core CLI to encode
        cmd = [
            self.server.morm_core_python,
            "-m", "morm_core.cli", "evidence",
            str(src),
            "--role", role,
            "--order-id", order_id,
            "--block-hash", block_hash,
            "--out", str(out_dir),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True,
                               cwd=str(self.server.morm_core_dir))
        if proc.returncode != 0:
            return self._json(500, {
                "error": "encode failed",
                "stderr": proc.stderr[-2000:], "stdout": proc.stdout[-500:],
            })
        # last line of stdout is the proof_hash (per cli.py contract)
        proof_hash = proc.stdout.strip().splitlines()[-1].strip()

        meta_dir = out_dir / f"{role}-source"
        first_cell = next(iter((meta_dir / "cells").glob("cell_*.webm")), None)
        # Run the AI tamper verifier in the morm-core venv (which has numpy
        # & Pillow). Fall back to "unknown" if it can't run.
        tamper: dict = {"tampered": False, "note": "verifier unavailable"}
        if first_cell:
            try:
                check = subprocess.run(
                    [self.server.morm_core_python, "-c",
                     "import json,sys; from morm_core.evidence import verify_evidence_video; "
                     f"print(json.dumps(verify_evidence_video(__import__('pathlib').Path({str(first_cell)!r}))))"],
                    capture_output=True, text=True, timeout=15,
                    cwd=str(self.server.morm_core_dir),
                )
                if check.returncode == 0:
                    tamper = json.loads(check.stdout.strip().splitlines()[-1])
            except Exception as e:
                tamper["error"] = str(e)

        return self._json(200, {
            "ok": True,
            "role": role,
            "order_id": order_id,
            "block_hash": block_hash,
            "proof_hash": proof_hash,
            "evidence_dir": str(meta_dir),
            "tamper": tamper,
        })
        return self._json(404, {"error": "not found"})

    def _dev_register(self, payload):
        cred_id = secrets.token_bytes(16)
        user_handle = secrets.token_urlsafe(16)
        seed, pub = l1crypto.keygen()
        server_share, client_share = split_key(seed)
        addr = l1crypto.address(pub)
        self.server.store.save_passkey(
            credential_id=cred_id, user_handle=user_handle,
            public_key=pub, sign_count=0,
            eth_address=addr, server_share_hex=server_share.hex(),
        )
        # auto-credit from MORM treasury so the new account can transact
        if self.server.fund_amount > 0:
            try:
                urllib.request.urlopen(urllib.request.Request(
                    self.server.morm_rpc.rstrip("/") + "/credit",
                    method="POST",
                    data=json.dumps({"to": addr, "amount": self.server.fund_amount}).encode(),
                    headers={"Content-Type": "application/json"},
                ), timeout=3).read()
            except Exception as e:
                sys.stderr.write(f"[fund] {e}\n")
        del seed
        return self._json(200, {
            "ok": True,
            "credential_id": base64.urlsafe_b64encode(cred_id).decode().rstrip("="),
            "morm_address": addr,
            "pubkey_hex": pub.hex(),
            "user_handle": user_handle,
            "client_share": client_share.hex(),
            "dev_mode": True,
        })

    def _dev_share(self, payload):
        cid_b64 = payload["credential_id"]
        cid = base64.urlsafe_b64decode(cid_b64 + "=" * (-len(cid_b64) % 4))
        saved = self.server.store.get_passkey(cid)
        if not saved:
            return self._json(404, {"ok": False, "error": "unknown credential"})
        return self._json(200, {
            "ok": True,
            "morm_address": saved["eth_address"],
            "pubkey_hex": saved["public_key"].hex(),
            "server_share": saved["server_share"],
        })

    # ---- demo treasury helpers (PoC only) -----------------------------

    def _morm_post(self, path: str, body: dict):
        req = urllib.request.Request(
            self.server.morm_rpc.rstrip("/") + path,
            method="POST",
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=3) as r:
            return json.loads(r.read())

    def _treasury_credit(self, payload):
        """Treasury → recipient TRANSFER tx (gossip-safe replacement for /credit)."""
        from morm_l1.tx import Transaction          # type: ignore
        from morm_l1 import crypto as l1crypto       # type: ignore
        try:
            seed_hex = self.server.treasury_seed_hex
            if not seed_hex:
                return self._json(403, {"ok": False, "error": "no treasury seed configured"})
            seed = bytes.fromhex(seed_hex)
            pub  = l1crypto.pubkey_from_seed(seed)
            addr = l1crypto.address(pub)
            nonce = json.loads(urllib.request.urlopen(
                self.server.morm_rpc.rstrip("/") + f"/account/{addr}").read())["nonce"]
            tx = Transaction.transfer(
                pub, nonce, to=payload["to"], amount=int(payload["amount"]),
            ).sign(seed)
            return self._json(200, self._morm_post("/tx", tx.to_dict()))
        except Exception as e:
            return self._json(400, {"ok": False, "error": str(e)})

    def _treasury_finalize(self, payload):
        """Treasury-signed finalize tx for the demo Shop flow."""
        from morm_l1.tx import Transaction          # type: ignore
        from morm_l1 import crypto as l1crypto       # type: ignore
        try:
            seed_hex = self.server.treasury_seed_hex
            if not seed_hex:
                return self._json(403, {"ok": False, "error": "no treasury seed configured"})
            seed = bytes.fromhex(seed_hex)
            pub  = l1crypto.pubkey_from_seed(seed)
            addr = l1crypto.address(pub)
            nonce = json.loads(urllib.request.urlopen(
                self.server.morm_rpc.rstrip("/") + f"/account/{addr}").read())["nonce"]
            tx = Transaction.finalize(
                pub, nonce, order_id=payload["order_id"], valid=bool(payload["valid"]),
            ).sign(seed)
            return self._json(200, {"ok": True,
                                     "morm_response": self._morm_post("/tx", tx.to_dict())})
        except Exception as e:
            return self._json(400, {"ok": False, "error": str(e)})

    def _relay_morm_tx(self, payload):
        tx_dict = payload.get("tx")
        if not tx_dict:
            return self._json(400, {"ok": False, "error": "missing tx"})
        try:
            req = urllib.request.Request(
                self.server.morm_rpc.rstrip("/") + "/tx",
                method="POST",
                data=json.dumps(tx_dict).encode(),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=3) as r:
                resp = json.loads(r.read())
            return self._json(200, {"ok": True, "morm_response": resp})
        except urllib.error.HTTPError as e:
            return self._json(400, {"ok": False, "error": f"morm rpc {e.code}: {e.read().decode()}"})
        except Exception as e:
            return self._json(400, {"ok": False, "error": str(e)})


class PasskeyMormServer(ThreadingHTTPServer):
    allow_reuse_address = True

    # ---- Phase 22 in-memory signaling -----------------------------------
    # Peers announce (peer_id → {content_id, cells, last_seen}). Other peers
    # query and exchange offers/answers/ICE through the inbox queue.
    #
    # Phase 26r/s DoS guards (SECURITY-DESIGN §1.5 26r/s):
    # - per-IP token-bucket rate limit on every /api/signal/* call. Default
    #   15 RPS sustained / 60 burst easily fits a normal client (announce
    #   every 5s + inbox poll every 200ms = ~5 RPS) but quickly squeezes a
    #   100-RPS flood. 429 Too Many Requests is returned by the handler.
    # - per-peer_id mailbox cap (default 256). Drops the OLDEST queued
    #   message on overflow so a polite peer's signaling can't be permanently
    #   wedged by an attacker spamming `/api/signal/send` to that target.
    # - global announced-peers cap (default 10000). When exceeded, the LRU
    #   peer (smallest last_seen) is evicted before inserting the new one,
    #   blocking the "1M peer_id announce" memory exhaustion attack.
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        import threading as _t
        self._sig_lock  = _t.Lock()
        self._sig_peers: dict = {}        # peer_id -> {...}
        self._sig_inbox: dict = {}        # peer_id -> [messages]
        self._sig_ttl   = 30              # seconds — peers expire if silent
        # 26r/s — caps. Overridden by main() from CLI flags.
        self.signal_rate_per_ip   = 15.0   # tokens/sec
        self.signal_burst_per_ip  = 60     # bucket size
        self.signal_mailbox_max   = 256    # messages per peer_id
        self.signal_peers_max     = 10_000 # announced peers concurrent
        self._rate_lock = _t.Lock()
        self._rate_buckets: dict = {}      # ip -> {tokens: float, last: float}

    def sig_rate_take(self, ip: str) -> bool:
        """Token-bucket per IP. Returns True if a token was available and
        consumed; False if the bucket is empty (caller should 429)."""
        import time as _time
        if not ip:
            return True   # local socketpair / unknown — fail open
        now = _time.time()
        with self._rate_lock:
            b = self._rate_buckets.get(ip)
            if b is None:
                b = {"tokens": float(self.signal_burst_per_ip), "last": now}
                self._rate_buckets[ip] = b
            elapsed = max(0.0, now - b["last"])
            b["tokens"] = min(float(self.signal_burst_per_ip),
                              b["tokens"] + elapsed * self.signal_rate_per_ip)
            b["last"] = now
            if b["tokens"] >= 1.0:
                b["tokens"] -= 1.0
                return True
            return False

    def sig_announce(self, peer_id: str, content_id: str, cells: list):
        import time as _time
        now = _time.time()
        with self._sig_lock:
            # 26s — global peers cap. Skip the eviction work if there's
            # room (common case). When over cap, drop stale TTL'd peers
            # first; if that's not enough, LRU-evict by last_seen.
            if (peer_id not in self._sig_peers
                and len(self._sig_peers) >= self.signal_peers_max):
                stale = [p for p, v in self._sig_peers.items()
                         if now - v["last_seen"] > self._sig_ttl]
                for p in stale:
                    self._sig_peers.pop(p, None)
                while len(self._sig_peers) >= self.signal_peers_max:
                    # LRU victim — smallest last_seen
                    lru_pid = min(self._sig_peers,
                                  key=lambda k: self._sig_peers[k]["last_seen"])
                    self._sig_peers.pop(lru_pid, None)
                    self._sig_inbox.pop(lru_pid, None)
            self._sig_peers[peer_id] = {
                "peer_id": peer_id,
                "content_id": content_id,
                "cells": list(cells or []),
                "last_seen": now,
            }

    def sig_peers_for(self, content_id: str, exclude: str | None = None) -> list:
        import time as _time
        now = _time.time()
        with self._sig_lock:
            stale = [p for p, v in self._sig_peers.items()
                     if now - v["last_seen"] > self._sig_ttl]
            for p in stale:
                self._sig_peers.pop(p, None)
            return [v for v in self._sig_peers.values()
                    if v["content_id"] == content_id and v["peer_id"] != exclude]

    def sig_send(self, to: str, payload: dict):
        with self._sig_lock:
            box = self._sig_inbox.setdefault(to, [])
            # 26s — drop the oldest message on overflow rather than reject
            # the new one. WebRTC offer/answer/ICE arrive newest-first in
            # importance; a stale offer the peer never picked up is far
            # less useful than the candidate ICE that just arrived.
            if len(box) >= self.signal_mailbox_max:
                box.pop(0)
            box.append(payload)

    def sig_inbox(self, peer_id: str) -> list:
        with self._sig_lock:
            msgs = self._sig_inbox.pop(peer_id, [])
        return msgs

    # ---- Phase 25Va: HLS content listing -------------------------------
    def list_hls_contents(self) -> list:
        root = getattr(self, "hls_storage_dir", None)
        if not root or not root.is_dir():
            return []
        out = []
        for cdir in sorted(root.iterdir()):
            if not cdir.is_dir():
                continue
            mf = cdir / "manifest.json"
            if not mf.is_file():
                continue
            try:
                m = json.loads(mf.read_text())
            except (OSError, json.JSONDecodeError):
                continue
            seg_counts = {k: len(v) for k, v in (m.get("segments") or {}).items()}
            out.append({
                "content_id": m.get("content_id") or cdir.name,
                "master_playlist_hash": m.get("master_playlist_hash"),
                "ladders": list(seg_counts.keys()),
                "segments_per_ladder": seg_counts,
            })
        return out

    # ---- Phase 22b: ICE config (STUN + optional TURN) -------------------
    # browser fetches GET /api/signal/ice?peer_id=<hex> at startup.
    # Server may be configured for:
    #   (a) STUN only (default — works on the same LAN, fails across NAT)
    #   (b) coturn use-auth-secret: ephemeral creds derived from a shared
    #       HMAC secret. username = "<expiry>:<peer_id>",
    #       credential = base64(HMAC-SHA1(secret, username))
    #   (c) static long-term credentials (less secure; for one-off demos)
    def ice_servers_for(self, peer_id: str) -> list:
        servers: list = []
        for u in self.stun_urls:
            servers.append({"urls": u})
        if self.turn_urls:
            entry = {"urls": list(self.turn_urls)}
            if self.turn_secret:
                ttl = self.turn_cred_ttl
                expiry = int(time.time()) + ttl
                uid = peer_id or secrets.token_hex(4)
                username = f"{expiry}:{uid}"
                mac = hmac.new(
                    self.turn_secret.encode(), username.encode(), hashlib.sha1,
                ).digest()
                entry["username"]   = username
                entry["credential"] = base64.b64encode(mac).decode()
            elif self.turn_static_username and self.turn_static_credential:
                entry["username"]   = self.turn_static_username
                entry["credential"] = self.turn_static_credential
            servers.append(entry)
        return servers


def _make_register_content_hook(morm_rpc: str, treasury_seed_hex: str | None):
    """Phase 25Va-finish: after a successful HLS encode, fire a
    REGISTER_CONTENT tx so VIEW_REWARD claims for those segments will apply
    on-chain (state.py:_tx_view_reward requires `contents.content_id`).

    Returns a callable suitable for `JobRegistry(post_encode_hook=...)`.
    No-op when treasury_seed_hex is None — the encode still succeeds, but
    chain-side claims will fail with "unknown content" until somebody
    registers the cid manually.
    """
    if not treasury_seed_hex:
        return None
    # imports deferred so the gateway still starts when morm-l1 is missing
    sys.path.insert(0, str(ROOT.parent / "morm-l1"))
    from morm_l1.tx import Transaction          # type: ignore
    from morm_l1 import crypto as l1crypto       # type: ignore

    def hook(st, manifest_path):
        try:
            mf = json.loads(manifest_path.read_text())
        except (OSError, json.JSONDecodeError) as e:
            st.log_tail.append(f"[register-content] manifest read error: {e}")
            return
        cid = mf.get("content_id") or st.content_id
        root_hash = mf.get("master_playlist_hash")
        if not (cid and root_hash):
            st.log_tail.append("[register-content] missing cid/root_hash, skipped")
            return
        seed = bytes.fromhex(treasury_seed_hex)
        pub = l1crypto.pubkey_from_seed(seed)
        addr = l1crypto.address(pub)
        try:
            with urllib.request.urlopen(
                f"{morm_rpc.rstrip('/')}/account/{addr}", timeout=3,
            ) as r:
                acct = json.loads(r.read())
            nonce = acct["nonce"]
        except Exception as e:  # noqa: BLE001
            st.log_tail.append(f"[register-content] nonce fetch failed: {e}")
            return
        tx = Transaction.register_content(
            pub, nonce, content_id=cid, root_hash=root_hash,
            generation_id=None,
        ).sign(seed)
        try:
            req = urllib.request.Request(
                f"{morm_rpc.rstrip('/')}/tx",
                method="POST",
                data=json.dumps(tx.to_dict()).encode(),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=3) as r:
                resp = json.loads(r.read())
            st.log_tail.append(
                f"[register-content] cid={cid[:12]}… root={root_hash[:12]}… "
                f"resp={json.dumps(resp)[:160]}"
            )
        except urllib.error.HTTPError as e:  # noqa: PERF203
            body = e.read().decode(errors="replace")[:300]
            st.log_tail.append(f"[register-content] HTTP {e.code}: {body}")
        except Exception as e:  # noqa: BLE001
            st.log_tail.append(f"[register-content] post error: {e}")

    return hook


def main(argv=None):
    # Phase 26w: production guard. When `MORM_PRODUCTION=1` is set in the
    # environment, `--dev-mode` is rejected at startup AND the dev-only
    # handlers (`/api/dev/register`, `/api/dev/share`) are inert no matter
    # what — even if some downstream code flips `server.dev_mode` after
    # construction. Treat it as a build-time switch even though we're
    # technically interpreted: deployers set it once on the prod host and
    # any human mistake (typing --dev-mode on the prod ssh) fails loudly.
    PRODUCTION_MODE = os.environ.get("MORM_PRODUCTION") == "1"

    p = argparse.ArgumentParser()
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8801)
    p.add_argument("--db", default=str(ROOT / "passkeys_morm.db"))
    p.add_argument("--morm-rpc", default="http://127.0.0.1:8900")
    p.add_argument("--fund-amount", type=int, default=100_000,
                   help="amount of micro-MORM to credit new accounts from treasury")
    p.add_argument("--dev-mode", action="store_true")
    p.add_argument("--treasury-seed", default=None,
                   help="hex 32-byte ed25519 seed to drive demo /api/treasury/* "
                        "helpers. ⚠ visible in `ps`; prefer --treasury-key-file "
                        "in production (Phase 26x).")
    # Phase 26x: load treasury seed from a 0600-mode file instead of CLI.
    # Prevents `ps` leakage on shared hosts. The file must be a single
    # line containing the 64-hex-char ed25519 seed (no whitespace beyond
    # surrounding newlines). Rejected with a clear error if mode > 0600.
    p.add_argument("--treasury-key-file", default=None,
                   help="path to a file (mode 0600) holding the treasury "
                        "ed25519 seed in hex. Replaces --treasury-seed for "
                        "production (avoids `ps` exposure).")
    p.add_argument("--morm-core-python",
                   default=str(ROOT.parent / "morm-core" / ".venv" / "bin" / "python"),
                   help="python with `morm_core` + numpy/Pillow available (for encode)")
    p.add_argument("--morm-core-dir",
                   default=str(ROOT.parent / "morm-core"),
                   help="cwd for the morm-core CLI invocation")
    # Phase 22b: WebRTC ICE config served via /api/signal/ice
    p.add_argument("--stun-url", action="append", default=None,
                   help="STUN URL (repeatable). Default: stun:stun.l.google.com:19302")
    p.add_argument("--turn-url", action="append", default=None,
                   help="TURN URL (repeatable, e.g. turn:host:3478?transport=udp)")
    p.add_argument("--turn-secret", default=None,
                   help="coturn use-auth-secret value (HMAC-SHA1). When set, "
                        "ephemeral creds are derived per peer.")
    p.add_argument("--turn-cred-ttl", type=int, default=600,
                   help="TTL (seconds) for ephemeral TURN credentials")
    p.add_argument("--turn-static-username", default=None,
                   help="Static TURN username (used only if --turn-secret unset)")
    p.add_argument("--turn-static-credential", default=None,
                   help="Static TURN credential (used only if --turn-secret unset)")
    # Phase 26r/s — DoS guards for the in-memory signaling layer.
    p.add_argument("--signal-rate-per-ip", type=float, default=15.0,
                   help="signaling RPS sustained per client IP (token-bucket "
                        "refill rate). Default 15 — fits a normal client "
                        "(announce 5s + inbox poll 200ms = ~5 RPS) with "
                        "headroom; squeezes flood traffic.")
    p.add_argument("--signal-burst-per-ip", type=int, default=60,
                   help="signaling burst capacity per client IP (token-bucket "
                        "max). Default 60.")
    p.add_argument("--signal-mailbox-max", type=int, default=256,
                   help="max queued signaling messages per peer_id; oldest "
                        "dropped on overflow. Default 256.")
    p.add_argument("--signal-peers-max", type=int, default=10000,
                   help="max concurrent announced peers; LRU-evict by "
                        "last_seen on overflow. Default 10000.")
    # Phase 26u/26v: Origin allowlist (CSRF protection + strict CORS).
    # Repeatable. When set, every POST whose `Origin` header is not in the
    # allowlist is rejected with 403, and OPTIONS/CORS headers echo only
    # the matched origin (never `*`). When unset, behaviour is the legacy
    # `Access-Control-Allow-Origin: *` and no CSRF check (suitable for
    # local development; NOT for production).
    p.add_argument("--allowed-origins", action="append", default=None,
                   help="Browser origins permitted to POST to this gateway "
                        "(repeatable, e.g. https://app.morm.io). When unset, "
                        "CORS=* and CSRF check off (LEGACY/DEV ONLY).")
    # Phase 25Va: HLS asset directory served under /api/video/<cid>/...
    # Layout (per docs/PHASE25-VIDEO.md §3.2):
    #   <hls-storage-dir>/<content_id>/master.m3u8
    #   <hls-storage-dir>/<content_id>/<resolution>/index.m3u8
    #   <hls-storage-dir>/<content_id>/<resolution>/init_*.mp4
    #   <hls-storage-dir>/<content_id>/<resolution>/seg_NNNNN.<vhash16>.m4s
    p.add_argument("--hls-storage-dir", default=None,
                   help="root dir holding `morm-core hls-encode` outputs. "
                        "When set, /api/video/<cid>/* serves master.m3u8, "
                        "sub-playlists, init segments and .m4s fragments. "
                        "Also acts as the storage root for /api/video/upload "
                        "(Phase 25Vb).")
    # Phase 25Vb: upload + encode pipeline knobs.
    p.add_argument("--encode-workers", type=int, default=1,
                   help="parallel hls-encode workers (default 1; ffmpeg "
                        "saturates a CPU at libx264 veryfast)")
    p.add_argument("--max-upload-mb", type=int, default=200,
                   help="POST /api/video/upload size cap in MB")
    # Phase 25Vc: opt-in CDN rewrite. Set this to e.g. https://cdn.morm.io
    # and the gateway will rewrite playlist URIs to absolute CDN URLs while
    # still serving everything from origin. Unset = pure origin mode (3原則:
    # 法人なし、自前運用が標準パス、CDN は加速層であり必須ではない)。
    p.add_argument("--cdn-base-url", default=None,
                   help="absolute base URL for the CDN edge (e.g. "
                        "https://cdn.morm.io). When set, .m3u8 responses are "
                        "rewritten so segment URIs hit the CDN. The origin "
                        "still serves all bytes unchanged.")
    # Phase 28a: bridge config for the /swap UI. Both flags are optional;
    # when unset, /swap renders a "bridge unavailable" hint instead of the
    # MetaMask form. The address is exposed via /api/morm/bridge.
    p.add_argument("--bridge-addr", default=None,
                   help="MORMBridge contract address (0x…40 hex). When set, "
                        "/swap is enabled and /api/morm/bridge advertises it.")
    p.add_argument("--evm-rpc", default="http://127.0.0.1:8545",
                   help="EVM JSON-RPC URL (anvil/mainnet) the /swap page "
                        "advertises so MetaMask can be auto-prompted to add "
                        "the network. Default http://127.0.0.1:8545 (anvil).")
    p.add_argument("--evm-chain-id", type=int, default=31337,
                   help="EVM chain id matching --evm-rpc. Default 31337 (anvil).")
    # Phase 28b: ERC-20 (USDC) bridge — second tab on /swap. Optional;
    # both addresses must be set together. The relayer needs the same
    # pair via argv to wire the TokenLocked listener + unlockToken caller.
    p.add_argument("--erc20-bridge-addr", default=None,
                   help="MORMBridgeERC20 contract address. When set together "
                        "with --usdc-addr, /swap shows a USDC tab.")
    p.add_argument("--usdc-addr", default=None,
                   help="MockUSDC (or production USDC) ERC-20 address. "
                        "Pairs with --erc20-bridge-addr.")
    args = p.parse_args(argv)

    # Phase 26w: production guard against accidental dev-mode in prod.
    if PRODUCTION_MODE and args.dev_mode:
        print("[fatal] MORM_PRODUCTION=1 is set; --dev-mode is forbidden. "
              "Unset MORM_PRODUCTION or remove --dev-mode.", file=sys.stderr)
        return 2

    # Phase 26x: prefer --treasury-key-file; refuse weak file modes.
    treasury_seed_hex = args.treasury_seed
    if args.treasury_key_file:
        if args.treasury_seed:
            print("[fatal] --treasury-seed and --treasury-key-file are "
                  "mutually exclusive.", file=sys.stderr)
            return 2
        try:
            kp = Path(args.treasury_key_file)
            mode = kp.stat().st_mode & 0o777
            if mode != 0o600:
                print(f"[fatal] --treasury-key-file {kp} mode is "
                      f"0o{mode:o}; expected 0o600. Run: "
                      f"chmod 600 {kp}", file=sys.stderr)
                return 2
            treasury_seed_hex = kp.read_text().strip()
            if len(treasury_seed_hex) != 64:
                print(f"[fatal] --treasury-key-file content is "
                      f"{len(treasury_seed_hex)} chars; expected 64 hex.",
                      file=sys.stderr)
                return 2
        except FileNotFoundError:
            print(f"[fatal] --treasury-key-file {args.treasury_key_file} "
                  f"not found.", file=sys.stderr)
            return 2

    httpd = PasskeyMormServer((args.host, args.port), Handler)
    httpd.store = authmod.AuthStore(Path(args.db))
    httpd.morm_rpc = args.morm_rpc
    httpd.fund_amount = args.fund_amount
    # Phase 26w: even if --dev-mode was passed locally, force False in
    # production. This is the runtime kill-switch for the gate at
    # `do_POST` line 212/214.
    httpd.dev_mode = bool(args.dev_mode and not PRODUCTION_MODE)
    httpd.treasury_seed_hex = treasury_seed_hex
    httpd.morm_core_python = args.morm_core_python
    httpd.morm_core_dir    = args.morm_core_dir
    httpd.stun_urls = args.stun_url or ["stun:stun.l.google.com:19302"]
    httpd.turn_urls = args.turn_url or []
    httpd.turn_secret = args.turn_secret
    httpd.turn_cred_ttl = args.turn_cred_ttl
    httpd.turn_static_username = args.turn_static_username
    httpd.turn_static_credential = args.turn_static_credential
    httpd.allowed_origins = (set(args.allowed_origins)
                             if args.allowed_origins else None)
    httpd.hls_storage_dir = (Path(args.hls_storage_dir).resolve()
                             if args.hls_storage_dir else None)
    # Phase 25Vb: storage abstraction + in-process job registry. Both are
    # only initialized when --hls-storage-dir is set, since they only make
    # sense for the HLS pipeline. The storage backend is selected via
    # MORM_STORAGE_BACKEND env (fs|s3); default fs uses --hls-storage-dir
    # as the root.
    if httpd.hls_storage_dir:
        httpd.upload_storage = storagemod.StorageBackend.from_env(
            default_root=httpd.hls_storage_dir)
        httpd.jobs = jobsmod.JobRegistry(
            max_workers=args.encode_workers,
            post_encode_hook=_make_register_content_hook(
                morm_rpc=args.morm_rpc,
                treasury_seed_hex=treasury_seed_hex,
            ),
        )
    else:
        httpd.upload_storage = None
        httpd.jobs = None
    httpd.max_upload_bytes = args.max_upload_mb * 1024 * 1024
    httpd.cdn_base_url = (args.cdn_base_url.rstrip("/")
                          if args.cdn_base_url else None)
    # Phase 28a — bridge config for /swap.
    httpd.bridge_addr   = args.bridge_addr
    httpd.evm_rpc_url   = args.evm_rpc
    httpd.evm_chain_id  = int(args.evm_chain_id) if args.evm_chain_id else None
    # Phase 28b — optional ERC-20 (USDC) bridge for the /swap "USDC" tab.
    httpd.erc20_bridge_addr = args.erc20_bridge_addr
    httpd.usdc_addr         = args.usdc_addr
    # Phase 26r/s — apply DoS-guard tuning from CLI.
    httpd.signal_rate_per_ip   = float(args.signal_rate_per_ip)
    httpd.signal_burst_per_ip  = int(args.signal_burst_per_ip)
    httpd.signal_mailbox_max   = int(args.signal_mailbox_max)
    httpd.signal_peers_max     = int(args.signal_peers_max)
    turn_status = ("auth-secret" if args.turn_secret
                   else ("static" if args.turn_static_username else "none"))
    csrf_status = ("legacy/* (no CSRF check)"
                   if not httpd.allowed_origins
                   else f"strict ({len(httpd.allowed_origins)} origins)")
    treasury_src = ("keyfile" if args.treasury_key_file else
                    "cli-arg" if args.treasury_seed else "none")
    hls_status = (f"on ({httpd.hls_storage_dir})"
                  if httpd.hls_storage_dir else "off")
    cdn_status = httpd.cdn_base_url or "off"
    bridge_status = (f"on ({httpd.bridge_addr[:10]}…@{httpd.evm_chain_id})"
                     if httpd.bridge_addr else "off")
    erc20_status = (f"on (bridge {httpd.erc20_bridge_addr[:10]}… usdc {httpd.usdc_addr[:10]}…)"
                    if httpd.erc20_bridge_addr and httpd.usdc_addr else "off")
    prod_marker = " PRODUCTION" if PRODUCTION_MODE else ""
    print(f"[passkey-morm]{prod_marker} http://{args.host}:{args.port}/  "
          f"morm={args.morm_rpc}  dev_mode={httpd.dev_mode}  "
          f"turn={len(httpd.turn_urls)}({turn_status})  cors={csrf_status}  "
          f"treasury={treasury_src}  hls={hls_status}  cdn={cdn_status}  "
          f"bridge={bridge_status}  erc20={erc20_status}  "
          f"signal_caps=rps:{httpd.signal_rate_per_ip}/"
          f"burst:{httpd.signal_burst_per_ip}/"
          f"mailbox:{httpd.signal_mailbox_max}/"
          f"peers:{httpd.signal_peers_max}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    os.chdir(ROOT)
    raise SystemExit(main())
