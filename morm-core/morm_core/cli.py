"""morm-core CLI: encode | screen | db-stats | db-gc."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .encoder import encode_cells
from .evidence import (
    encode_evidence, evidence_root_hash, latest_block_hash, write_evidence_meta,
)
from .hls_encoder import encode_hls
from .manifest import build_manifest
from .screening import gc_rejected, open_db, screen, stats

DEFAULT_DB = Path("output/morm.db")


def cmd_encode(args: argparse.Namespace) -> int:
    src = Path(args.input).resolve()
    if not src.exists():
        print(f"input not found: {src}", file=sys.stderr)
        return 2

    out_root = Path(args.out).resolve()
    cells_dir = out_root / src.stem / "cells"
    print(f"[1/3] encoding {src.name} → {cells_dir}")
    cells = encode_cells(src, cells_dir)
    print(f"      {len(cells)} cells written")

    print("[2/3] hashing + V-Hash")
    manifest = build_manifest(
        cells_dir,
        creator_id=args.creator,
        generation_id=args.generation_id,
        parent_block_hash=args.parent_block_hash,
    )

    manifest_path = out_root / src.stem / "manifest.json"
    manifest_path.write_text(manifest.to_json(), encoding="utf-8")
    print(f"[3/3] manifest → {manifest_path}")
    print(f"      content_id={manifest.content_id[:16]}…")
    print(f"      root_hash ={manifest.root_hash[:16]}…")
    return 0


def cmd_screen(args: argparse.Namespace) -> int:
    manifest_path = Path(args.manifest).resolve()
    if not manifest_path.exists():
        print(f"manifest not found: {manifest_path}", file=sys.stderr)
        return 2
    cells_dir = manifest_path.parent / "cells"
    conn = open_db(Path(args.db))
    try:
        result = screen(conn, manifest_path, cells_dir=cells_dir)
    finally:
        conn.close()

    print(f"content_id={result.content_id[:16]}…")
    if result.accepted:
        print(f"  ✓ ACCEPTED  ({result.total_cells} cells registered)")
        return 0
    print(f"  ✗ REJECTED  reason={result.reason}")
    if result.duplicate_of:
        print(f"             duplicate_of={result.duplicate_of[:16]}…")
    if result.matched_cells:
        print(f"             matched={result.matched_cells}/{result.total_cells} cells")
    return 1


def cmd_db_stats(args: argparse.Namespace) -> int:
    conn = open_db(Path(args.db))
    try:
        s = stats(conn)
    finally:
        conn.close()
    print(json.dumps(s, indent=2))
    return 0


def cmd_evidence(args: argparse.Namespace) -> int:
    src = Path(args.input).resolve()
    if not src.exists():
        print(f"input not found: {src}", file=sys.stderr)
        return 2

    if args.block_hash:
        block_hash = args.block_hash
        block_number = -1
    else:
        if not args.rpc_url:
            print("either --block-hash or --rpc-url required", file=sys.stderr)
            return 2
        block_hash, block_number = latest_block_hash(args.rpc_url)

    out_dir = Path(args.out).resolve() / f"{args.role}-{src.stem}"
    cells_dir = out_dir / "cells"
    print(f"[1/3] encoding {args.role} evidence → {cells_dir}")
    print(f"      bound to order={args.order_id[:18]}…  block={block_hash[:18]}…  (#{block_number})")
    cells = encode_evidence(src, cells_dir, args.role, args.order_id, block_hash)
    print(f"      {len(cells)} cells written")

    print("[2/3] computing evidence root hash")
    root = evidence_root_hash(cells, args.role, args.order_id, block_hash)
    print(f"      proof_hash = {root}")

    print("[3/3] sidecar metadata")
    meta = write_evidence_meta(
        out_dir,
        role=args.role,
        order_id=args.order_id,
        block_hash=block_hash,
        block_number=block_number,
        proof_hash=root,
        cells=[p.name for p in cells],
    )
    print(f"      {meta}")
    print()
    print(root)  # last line is the bytes32 — easy to capture from shell
    return 0


def cmd_hls_encode(args: argparse.Namespace) -> int:
    src = Path(args.input).resolve()
    if not src.exists():
        print(f"input not found: {src}", file=sys.stderr)
        return 2
    out_root = Path(args.out).resolve()
    out_root.mkdir(parents=True, exist_ok=True)
    print(f"[1/2] HLS encoding {src.name} → {out_root}/<content_id>/")
    manifest = encode_hls(src, out_root, content_id=args.content_id)
    n_files = sum(1 + len(segs) for segs in manifest.segments.values()) + 1
    print(f"      content_id    = {manifest.content_id}")
    print(f"      master_pl_hash= {manifest.master_playlist_hash[:16]}…")
    for rung, segs in manifest.segments.items():
        print(f"      {rung:<5}: {len(segs)} segments")
    print(f"[2/2] manifest → {out_root / manifest.content_id / 'manifest.json'}")
    print(f"      total files (m3u8/init/segs) ≈ {n_files}")
    print(manifest.content_id)
    return 0


def cmd_db_gc(args: argparse.Namespace) -> int:
    conn = open_db(Path(args.db))
    try:
        deleted = gc_rejected(conn, dry_run=args.dry_run)
    finally:
        conn.close()
    label = "WOULD DELETE" if args.dry_run else "DELETED"
    print(f"{label} {len(deleted)} rejected cell directories:")
    for p in deleted:
        print(f"  - {p}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="morm-core")
    sub = p.add_subparsers(dest="cmd", required=True)

    enc = sub.add_parser("encode", help="split video into 3-second WebM cells + manifest")
    enc.add_argument("input")
    enc.add_argument("--out", default="output")
    enc.add_argument("--creator", default="anon")
    enc.add_argument("--generation-id", default=None,
                     help="non-null = AI-generated; recorded on-chain as origin marker")
    enc.add_argument("--parent-block-hash", default=None)
    enc.set_defaults(func=cmd_encode)

    scr = sub.add_parser("screen", help="submit a manifest to the screening DB")
    scr.add_argument("manifest")
    scr.add_argument("--db", default=str(DEFAULT_DB))
    scr.set_defaults(func=cmd_screen)

    st = sub.add_parser("db-stats", help="show DB stats")
    st.add_argument("--db", default=str(DEFAULT_DB))
    st.set_defaults(func=cmd_db_stats)

    ev = sub.add_parser("evidence",
                         help="encode packing/opening evidence cells with on-chain block-hash watermark")
    ev.add_argument("input", help="raw video to wrap as evidence")
    ev.add_argument("--role", choices=["packing", "opening"], required=True)
    ev.add_argument("--order-id", required=True,
                    help="order id (bytes32 hex) the evidence is bound to")
    ev.add_argument("--block-hash", default=None,
                    help="explicit block hash; if omitted, fetched from --rpc-url")
    ev.add_argument("--rpc-url", default="http://127.0.0.1:8545")
    ev.add_argument("--out", default="output/evidence")
    ev.set_defaults(func=cmd_evidence)

    hls = sub.add_parser(
        "hls-encode",
        help="Phase 25Va: encode video into ABR HLS/CMAF (1080p/720p/480p/360p)",
    )
    hls.add_argument("input")
    hls.add_argument("--out", default="output/hls",
                     help="root dir; the encoder creates <out>/<content_id>/...")
    hls.add_argument("--content-id", default=None,
                     help="override content id (default: sha256(input)[:16])")
    hls.set_defaults(func=cmd_hls_encode)

    gc = sub.add_parser("db-gc", help="garbage-collect cells of rejected submissions")
    gc.add_argument("--db", default=str(DEFAULT_DB))
    gc.add_argument("--dry-run", action="store_true")
    gc.set_defaults(func=cmd_db_gc)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
