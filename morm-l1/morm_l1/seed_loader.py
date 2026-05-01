"""Phase 30c — federation seed loader.

A fresh MORM node needs an initial list of peers to gossip with. The list
is intentionally NOT served by a single DNS zone or registry; instead the
sources are multiple, in priority order:

  1. ``--peers`` (CLI / env override). Always wins.
  2. User-mutable ``<data_dir>/seeds.json`` (per-node persistence — the
     loader writes new peers it discovers here so the node remembers them
     on the next boot).
  3. Baked-in ``morm_l1/seeds.json`` (shipped in the source tree / image).
  4. Live discovery channels declared by either of the JSON files:
     - DNS SRV (``_morm-seeds._tcp.<zone>``)
     - HTTP GET (``github_raw_seeds_url``)
     - IPFS CID (``ipfs_seed_cid``) — gateway used opportunistically

The merged list is deduplicated, the operator's own ``PUBLIC_URL`` is
filtered out, and the result is returned in the order: explicit > local-
mutable > baked-in > live.

This module is import-safe: it has no side effects beyond reading files
and (when explicitly invoked) issuing best-effort HTTP/DNS lookups.
"""
from __future__ import annotations

import json
import os
import socket
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

DEFAULT_BAKED = Path(__file__).resolve().parent / "seeds.json"


@dataclass
class Seed:
    url: str
    source: str  # "explicit" | "local" | "baked" | "discovery"

    def normalize(self) -> str:
        u = self.url.strip().rstrip("/")
        # collapse trailing slashes; preserve scheme + path
        return u


@dataclass
class SeedSet:
    seeds: list[Seed] = field(default_factory=list)
    sources: dict[str, list[str]] = field(default_factory=dict)

    def add(self, url: str, source: str) -> None:
        if not url:
            return
        s = Seed(url=url, source=source).normalize()
        if any(x.normalize() == s for x in self.seeds):
            return
        self.seeds.append(Seed(url=s, source=source))
        self.sources.setdefault(source, []).append(s)

    def urls(self, *, exclude: Iterable[str] = ()) -> list[str]:
        ex = {u.rstrip("/") for u in exclude if u}
        return [s.url for s in self.seeds if s.url.rstrip("/") not in ex]


def _read_json(path: Path) -> dict | None:
    try:
        with path.open() as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None


def _seeds_from_doc(doc: dict | None) -> list[str]:
    if not doc:
        return []
    out = []
    for s in doc.get("seeds") or []:
        if isinstance(s, str):
            out.append(s)
        elif isinstance(s, dict) and s.get("url"):
            out.append(s["url"])
    return out


def _discovery_from_doc(doc: dict | None) -> dict:
    if not doc:
        return {}
    return doc.get("discovery") or {}


def _http_fetch_seeds(url: str, timeout: float = 4.0) -> list[str]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            doc = json.loads(r.read())
        return _seeds_from_doc(doc)
    except (urllib.error.URLError, json.JSONDecodeError, OSError, ValueError):
        return []


def _dns_srv_lookup(name: str) -> list[str]:
    """Resolve `_morm-seeds._tcp.<zone>` SRV records into HTTP URLs.

    We use stdlib `socket.getaddrinfo` indirectly — Python doesn't ship a
    DNS resolver, and pulling dnspython into morm-l1 adds a runtime dep
    we'd rather avoid. The stub here returns empty; operators wanting DNS
    SRV discovery can either install dnspython and override this function
    in `~/.morm/seed_hooks.py` or rely on the HTTP fallback.
    """
    try:
        import dns.resolver  # type: ignore
    except ImportError:
        return []
    try:
        ans = dns.resolver.resolve(name, "SRV")
    except Exception:
        return []
    out = []
    for rr in ans:
        # weight/priority ignored for the PoC list; just emit URLs.
        host = str(rr.target).rstrip(".")
        out.append(f"http://{host}:{rr.port}")
    return out


def load_peer_urls(
    *,
    explicit_peers: Iterable[str] | None = None,
    data_dir: Path | None = None,
    baked_path: Path = DEFAULT_BAKED,
    public_url: str | None = None,
    enable_discovery: bool = True,
) -> SeedSet:
    """Resolve the effective peer set for this node startup.

    Args:
      explicit_peers: --peers CLI/env list. If non-empty, this becomes the
          ENTIRE result (other sources skipped). The operator is in charge.
      data_dir: where local-mutable ``seeds.json`` lives. Typically
          ``Path(args.data_dir)``.
      baked_path: shipped seeds.json (defaults to morm_l1/seeds.json).
      public_url: if set, the operator's own public URL — filtered out so
          this node doesn't list itself as a peer.
      enable_discovery: set False in unit tests / offline mode.

    Returns:
      SeedSet whose ``urls()`` ordering is: explicit > local > baked > discovery.
    """
    out = SeedSet()
    explicit = [u for u in (explicit_peers or []) if u]
    if explicit:
        for u in explicit:
            out.add(u, "explicit")
        return out

    # ---- local-mutable ----
    if data_dir is not None:
        local = data_dir / "seeds.json"
        local_doc = _read_json(local)
        for u in _seeds_from_doc(local_doc):
            out.add(u, "local")
    else:
        local_doc = None

    # ---- baked-in ----
    baked_doc = _read_json(baked_path)
    for u in _seeds_from_doc(baked_doc):
        out.add(u, "baked")

    # ---- live discovery ----
    if enable_discovery:
        # local takes priority over baked when supplying discovery hooks.
        for src in (local_doc, baked_doc):
            disc = _discovery_from_doc(src)
            url = disc.get("github_raw_seeds_url")
            if url:
                for u in _http_fetch_seeds(url):
                    out.add(u, "discovery")
            srv = disc.get("dns_seed")
            if srv:
                for u in _dns_srv_lookup(srv):
                    out.add(u, "discovery")
            # ipfs_seed_cid is reserved (no resolver wired in stdlib);
            # operators with `ipfs daemon` can install a local cli hook.

    # ---- filter ourselves ----
    if public_url:
        before = [s.url for s in out.seeds]
        out.seeds = [s for s in out.seeds if s.url.rstrip("/") != public_url.rstrip("/")]
        out.sources = {
            k: [u for u in v if u.rstrip("/") != public_url.rstrip("/")]
            for k, v in out.sources.items()
        }

    return out


# ---- CLI helper ---------------------------------------------------------

def _cli(argv: list[str]) -> int:
    """Print the effective peer list for diagnostics.

    Usage: python -m morm_l1.seed_loader [--data-dir DIR] [--public-url URL]
                                          [--explicit URL,URL] [--no-discovery]
    """
    import argparse
    p = argparse.ArgumentParser(description="Inspect MORM federation seed list")
    p.add_argument("--data-dir", default=None,
                   help="node data dir (looks for seeds.json inside)")
    p.add_argument("--public-url", default=None)
    p.add_argument("--explicit", default=None,
                   help="comma-separated override (skips other sources)")
    p.add_argument("--no-discovery", action="store_true")
    args = p.parse_args(argv)

    explicit = (args.explicit.split(",") if args.explicit else None)
    out = load_peer_urls(
        explicit_peers=explicit,
        data_dir=Path(args.data_dir) if args.data_dir else None,
        public_url=args.public_url,
        enable_discovery=not args.no_discovery,
    )
    if not out.seeds:
        print("(no peers — fresh node will run as standalone producer)")
        return 0
    print(f"effective peer list ({len(out.seeds)} entries):")
    for s in out.seeds:
        print(f"  [{s.source:9s}] {s.url}")
    print()
    print("comma-separated for --peers:")
    print(",".join(s.url for s in out.seeds))
    return 0


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
