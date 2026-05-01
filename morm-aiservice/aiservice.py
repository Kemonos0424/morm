"""MORM AI Service — deterministic video generation + Generation ID issuance.

Spec ref: MORM.md §5 — "AIが動画を生成する際、モデルのシード値・プロンプト・
日時を組み合わせた一意の Generation ID を発行。MORM Chain上に直接書き込まれ
他者が同じAIで似た動画を作っても異なるIDになる。初期と認識できる。"

This service holds an ed25519 identity keypair. Each generation is:
  ① deterministic: same (prompt, seed) → same video bytes
  ② signed: generation_id = sha256(prompt | seed | timestamp_bucket)
            attestation = ed25519_sign(svc_seed, generation_id || cid)
  ③ verifiable: anyone with the service's public key can verify the
     attestation; the L1 enforces that the ai_service is a known publisher.

The actual "model" here is a deterministic procedural pattern (color +
text overlay) so we never depend on a real GPU; the protocol-level guarantees
are what matter for the demo.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / "morm-l1"))
from morm_l1 import crypto                                  # noqa: E402

KEY_PATH = ROOT / "service-key.json"
OUT_ROOT = ROOT / "generated"
TS_BUCKET = 60   # 1-minute bucket so re-runs in the same minute are stable


def _hex(b: bytes) -> str: return b.hex()


def get_or_create_keypair() -> tuple[bytes, bytes]:
    """Persistent service identity. Same key per run."""
    if KEY_PATH.exists():
        d = json.loads(KEY_PATH.read_text())
        return bytes.fromhex(d["seed"]), bytes.fromhex(d["pubkey"])
    seed, pub = crypto.keygen()
    KEY_PATH.write_text(json.dumps({
        "seed": _hex(seed), "pubkey": _hex(pub),
        "address": crypto.address(pub),
    }, indent=2))
    return seed, pub


def generation_id(prompt: str, model_seed: int, ts_bucket: int) -> str:
    """SHA-256 over (prompt | model_seed | ts_bucket). 32-byte hex."""
    h = hashlib.sha256()
    h.update(b"MORM-GEN-ID|")
    h.update(prompt.encode())
    h.update(b"|")
    h.update(str(int(model_seed)).encode())
    h.update(b"|")
    h.update(str(int(ts_bucket)).encode())
    return "0x" + h.hexdigest()


def deterministic_video(prompt: str, model_seed: int, out_path: Path) -> Path:
    """Generate a 6-second 480x270 video deterministic over (prompt, seed).

    PoC stand-in for a real video diffusion model: the seed picks a color
    palette + a per-frame offset; the prompt becomes a baked-in label so the
    same inputs produce identical bytes.
    """
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg not in PATH")
    rng = (int(model_seed) ^ hash(prompt)) & 0xFFFFFFFF
    r = (rng >> 16) & 0xFF
    g = (rng >> 8)  & 0xFF
    b =  rng        & 0xFF
    color = f"0x{r:02x}{g:02x}{b:02x}"
    label = f"MORM-AI gen-id={generation_id(prompt, model_seed, 0)[:18]}"

    # text on a colored background, 30fps, 6s
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "lavfi", "-i", f"color=c={color}:size=480x270:rate=30",
        "-vf", (f"drawtext=text='{label.replace(':',' ')}':"
                f"fontfile=/System/Library/Fonts/Monaco.ttf:"
                f"fontsize=18:fontcolor=white:x=12:y=12"),
        "-t", "6",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        str(out_path),
    ]
    subprocess.run(cmd, check=True)
    return out_path


def attest(seed: bytes, generation_id_hex: str, content_id_hex: str) -> str:
    """Sign (gen_id || cid) so the chain can prove this AI service issued it."""
    msg = bytes.fromhex(generation_id_hex.removeprefix("0x"))
    msg += bytes.fromhex(content_id_hex.removeprefix("0x"))
    sig = crypto.sign(seed, msg)
    return _hex(sig)


def cmd_keygen(_):
    seed, pub = get_or_create_keypair()
    print(json.dumps({
        "seed":    _hex(seed),
        "pubkey":  _hex(pub),
        "address": crypto.address(pub),
    }, indent=2))


def cmd_generate(args):
    seed, pub = get_or_create_keypair()
    ts_bucket = int(time.time() // TS_BUCKET) if not args.bucket else int(args.bucket)
    gid = generation_id(args.prompt, args.seed, ts_bucket)

    out_dir = OUT_ROOT / gid[2:18]
    out_dir.mkdir(parents=True, exist_ok=True)
    video = deterministic_video(args.prompt, args.seed, out_dir / "video.mp4")
    # the cid will be the sha256 of the bytes — caller can also recompute
    cid = "0x" + hashlib.sha256(video.read_bytes()).hexdigest()
    sig = attest(seed, gid, cid)

    manifest = {
        "ai_service_pubkey": _hex(pub),
        "ai_service_address": crypto.address(pub),
        "prompt": args.prompt,
        "model_seed": int(args.seed),
        "ts_bucket": ts_bucket,
        "generation_id": gid,
        "content_id": cid,
        "signature": sig,
        "video": str(video),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(json.dumps(manifest, indent=2))


def cmd_verify(args):
    """Standalone verification: useful for off-chain consumers."""
    m = json.loads(Path(args.manifest).read_text())
    msg  = bytes.fromhex(m["generation_id"].removeprefix("0x"))
    msg += bytes.fromhex(m["content_id"].removeprefix("0x"))
    pub  = bytes.fromhex(m["ai_service_pubkey"])
    sig  = bytes.fromhex(m["signature"])
    ok = crypto.verify(pub, sig, msg)
    expected_gid = generation_id(m["prompt"], m["model_seed"], m["ts_bucket"])
    print(json.dumps({
        "signature_valid": ok,
        "generation_id_recomputed": expected_gid,
        "matches": expected_gid == m["generation_id"],
    }, indent=2))


def main(argv=None):
    p = argparse.ArgumentParser(prog="morm-ai")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("keygen").set_defaults(func=cmd_keygen)
    g = sub.add_parser("generate")
    g.add_argument("--prompt", required=True)
    g.add_argument("--seed", type=int, required=True,
                   help="model seed; combined with prompt for determinism")
    g.add_argument("--bucket", default=None,
                   help="explicit ts_bucket (override; for reproducibility)")
    g.set_defaults(func=cmd_generate)
    v = sub.add_parser("verify")
    v.add_argument("manifest")
    v.set_defaults(func=cmd_verify)
    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
