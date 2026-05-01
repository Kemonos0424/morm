"""MORM Edge Node — origin or mirror, with lazy P2P cache propagation.

Spec ref: MORM.md §2 ("階層型P2Pメッシュ"). Two roles:

  - origin: holds the screening DB and the canonical cells dir; this is the
    only node that can answer /api/contents and /api/manifest.
  - mirror: starts empty; on a /api/cell miss it asks its peers (round-robin)
    until one returns 200, then writes the body to its own storage and
    serves it. Subsequent requests are local hits — the cell has propagated.

A single `/api/node/info` endpoint exposes role, cell count, hits, misses
and last-peer-asked so the player UI can show the swarm in action.
"""
from __future__ import annotations

import argparse
import json
import mimetypes
import os
import re
import sqlite3
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "static"


class Handler(BaseHTTPRequestHandler):
    server_version = "MORMEdge/0.2"

    def log_message(self, fmt, *args):
        sys.stderr.write(f"[{self.server.node_id}] {fmt % args}\n")

    def _add_cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")

    def do_OPTIONS(self):
        self.send_response(204)
        self._add_cors()
        self.send_header("Access-Control-Allow-Headers", "Range")
        self.end_headers()

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/":
            return self._serve_static("index.html")
        if path.startswith("/static/"):
            return self._serve_static(path[len("/static/"):])
        if path == "/api/node/info":
            return self._api_node_info()
        if path == "/api/contents":
            return self._api_contents()
        m = re.match(r"^/api/manifest/([0-9a-f]+)$", path)
        if m:
            return self._api_manifest(m.group(1))
        m = re.match(r"^/api/cell/([0-9a-f]+)/(\d+)$", path)
        if m:
            return self._api_cell(m.group(1), int(m.group(2)))
        self._not_found()

    # -- API --------------------------------------------------------------

    def _api_node_info(self):
        s = self.server
        self._send_json(200, {
            "node_id": s.node_id,
            "role": s.role,
            "peers": s.peers,
            "cells_held": s.cells_held(),
            "hits": s.hits,
            "misses": s.misses,
            "fills": s.fills,
            "last_peer": s.last_peer,
        })

    def _api_contents(self):
        if self.server.role == "origin":
            conn = sqlite3.connect(self.server.db_path)
            rows = conn.execute(
                "SELECT content_id, creator_id, generation_id, accepted_at "
                "FROM contents WHERE status = 'accepted' ORDER BY accepted_at DESC"
            ).fetchall()
            conn.close()
            items = [
                {"content_id": r[0], "creator_id": r[1],
                 "generation_id": r[2], "accepted_at": r[3]}
                for r in rows
            ]
            return self._send_json(200, {"contents": items, "served_by": self.server.node_id})
        # mirror: proxy from first reachable peer
        body, status = self.server.peer_get_json("/api/contents")
        return self._send_json(status, body if body else {"contents": []})

    def _api_manifest(self, content_id: str):
        if self.server.role == "origin":
            manifest_path = self.server.find_manifest(content_id)
            if not manifest_path:
                return self._not_found()
            data = json.loads(manifest_path.read_text())
            data["cell_url_template"] = f"/api/cell/{content_id}/{{index}}"
            data["served_by"] = self.server.node_id
            return self._send_json(200, data)
        body, status = self.server.peer_get_json(f"/api/manifest/{content_id}")
        return self._send_json(status, body if body else {})

    def _api_cell(self, content_id: str, index: int):
        cell_path = self.server.local_cell(content_id, index)
        if cell_path and cell_path.exists():
            self.server.hits += 1
            self.send_response(200)
            self._add_cors()
            self.send_header("X-MORM-Served-By", self.server.node_id)
            self.send_header("X-MORM-Cache", "HIT")
            return self._serve_range(cell_path, "video/webm", already_started=True)

        # miss → ask peers (mirror only). Origin shouldn't reach here for valid cells.
        self.server.misses += 1
        if self.server.role == "origin":
            return self._not_found()

        body, served_by = self.server.peer_get_bytes(f"/api/cell/{content_id}/{index}")
        if not body:
            return self._not_found()

        # write through to local storage so the cell propagates
        self.server.cache_cell(content_id, index, body)
        self.server.fills += 1

        self.send_response(200)
        self._add_cors()
        self.send_header("Content-Type", "video/webm")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Cache-Control", "public, max-age=60")
        self.send_header("X-MORM-Served-By", self.server.node_id)
        self.send_header("X-MORM-Cache", "FILL")
        self.send_header("X-MORM-Origin-Peer", served_by)
        self.end_headers()
        self.wfile.write(body)

    # -- helpers ----------------------------------------------------------

    def _serve_static(self, name: str):
        target = (STATIC / name).resolve()
        if not str(target).startswith(str(STATIC)) or not target.is_file():
            return self._not_found()
        mime = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        body = target.read_bytes()
        self.send_response(200)
        self._add_cors()
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _serve_range(self, path: Path, mime: str, already_started: bool = False):
        size = path.stat().st_size
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
        if not already_started:
            self.send_response(206 if partial else 200)
            self._add_cors()
        elif partial:
            # we already sent 200; remove `partial` since we can't downgrade.
            partial = False
        self.send_header("Content-Type", mime)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(length))
        if partial:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.send_header("Cache-Control", "public, max-age=60")
        self.end_headers()
        with path.open("rb") as f:
            f.seek(start)
            remaining = length
            while remaining > 0:
                chunk = f.read(min(64 * 1024, remaining))
                if not chunk:
                    break
                self.wfile.write(chunk)
                remaining -= len(chunk)

    def _send_json(self, status: int, payload):
        body = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(status)
        self._add_cors()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _not_found(self):
        self.send_response(404)
        self._add_cors()
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"not found\n")


class EdgeServer(ThreadingHTTPServer):
    allow_reuse_address = True

    def __init__(self, *args, role, node_id, db_path, storage_dir, peers, **kw):
        super().__init__(*args, **kw)
        self.role = role
        self.node_id = node_id
        self.db_path = db_path
        self.storage_dir = Path(storage_dir).resolve()
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.peers: list[str] = peers
        self.hits = 0
        self.misses = 0
        self.fills = 0
        self.last_peer = None
        self._lock = threading.Lock()

    def cells_held(self) -> int:
        if self.role == "origin":
            # count cells that the DB knows about and that exist on disk
            try:
                conn = sqlite3.connect(self.db_path)
                rows = conn.execute(
                    "SELECT cells_dir FROM contents WHERE status='accepted'"
                ).fetchall()
                conn.close()
                n = 0
                for (d,) in rows:
                    if d:
                        n += len(list(Path(d).glob("cell_*.webm")))
                return n
            except sqlite3.Error:
                return 0
        return len(list(self.storage_dir.rglob("cell_*.webm")))

    def find_manifest(self, content_id: str) -> Path | None:
        if self.role != "origin":
            return None
        try:
            conn = sqlite3.connect(self.db_path)
            row = conn.execute(
                "SELECT cells_dir FROM contents WHERE content_id = ? AND status='accepted'",
                (content_id,),
            ).fetchone()
            conn.close()
            if not row or not row[0]:
                return None
            return Path(row[0]).parent / "manifest.json"
        except sqlite3.Error:
            return None

    def local_cell(self, content_id: str, index: int) -> Path | None:
        if self.role == "origin":
            try:
                conn = sqlite3.connect(self.db_path)
                row = conn.execute(
                    "SELECT cells_dir FROM contents WHERE content_id = ? AND status='accepted'",
                    (content_id,),
                ).fetchone()
                conn.close()
                if not row or not row[0]:
                    return None
                return Path(row[0]) / f"cell_{index:04d}.webm"
            except sqlite3.Error:
                return None
        # mirror: use storage_dir/<cid>/cell_NNNN.webm
        return self.storage_dir / content_id / f"cell_{index:04d}.webm"

    def cache_cell(self, content_id: str, index: int, data: bytes):
        target = self.storage_dir / content_id / f"cell_{index:04d}.webm"
        target.parent.mkdir(parents=True, exist_ok=True)
        with self._lock, target.open("wb") as f:
            f.write(data)

    def peer_get_json(self, path: str, timeout: float = 3.0) -> tuple[dict | None, int]:
        for peer in self.peers:
            url = peer.rstrip("/") + path
            try:
                with urllib.request.urlopen(url, timeout=timeout) as r:
                    self.last_peer = peer
                    return json.loads(r.read().decode()), r.status
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
                continue
        return None, 502

    def peer_get_bytes(self, path: str, timeout: float = 5.0) -> tuple[bytes | None, str | None]:
        for peer in self.peers:
            url = peer.rstrip("/") + path
            try:
                with urllib.request.urlopen(url, timeout=timeout) as r:
                    if r.status == 200:
                        self.last_peer = peer
                        return r.read(), peer
            except (urllib.error.URLError, TimeoutError):
                continue
        return None, None


def main(argv=None):
    p = argparse.ArgumentParser(description="MORM edge node (origin or mirror)")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, required=True)
    p.add_argument("--node-id", required=True)
    p.add_argument("--role", choices=["origin", "mirror"], required=True)
    p.add_argument("--db", default=None,
                   help="screening DB (origin only)")
    p.add_argument("--storage-dir", default=None,
                   help="local cell storage (mirror only). default: ./storage/<node-id>")
    p.add_argument("--peers", default="",
                   help="comma-separated peer URLs to fall back to")
    args = p.parse_args(argv)

    if args.role == "origin":
        if not args.db:
            print("--db required for origin role", file=sys.stderr); return 2
        db_abs = Path(args.db).resolve()
        if not db_abs.exists():
            print(f"DB not found: {db_abs}", file=sys.stderr); return 2
        db_path = str(db_abs)
        storage = ROOT / "storage" / args.node_id
    else:
        db_path = None
        storage = Path(args.storage_dir).resolve() if args.storage_dir \
                  else (ROOT / "storage" / args.node_id)

    peers = [u.strip() for u in args.peers.split(",") if u.strip()]
    httpd = EdgeServer(
        (args.host, args.port), Handler,
        role=args.role, node_id=args.node_id,
        db_path=db_path, storage_dir=storage, peers=peers,
    )
    print(f"[{args.node_id}] {args.role.upper()} on http://{args.host}:{args.port}/")
    print(f"           storage={storage}  peers={peers}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    os.chdir(ROOT)
    raise SystemExit(main())
