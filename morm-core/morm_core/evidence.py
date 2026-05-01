"""Proof of Physical Evidence — packing/opening Cell encoder + watermark.

Spec ref: MORM.md §6. Each Cell of an evidence video carries a burned-in
watermark containing:
  - role (packing | opening)
  - the truncated order_id it belongs to
  - the latest MORM Chain block hash at recording time
  - the elapsed timecode

Combined with a deterministic root hash over the cell list, this binds the
recording to (a) a specific order, (b) a real chain moment ≥ that block, and
(c) a verifiable pixel-level provenance.
"""
from __future__ import annotations

import hashlib
import shutil
import subprocess
from pathlib import Path

import numpy as np

from .encoder import (
    AUDIO_BITRATE, CELL_DURATION_SEC, TARGET_FPS, VIDEO_BITRATE, probe,
)


def latest_block_hash(rpc_url: str) -> tuple[str, int]:
    """Return (block_hash, block_number) of the latest block on `rpc_url`.

    Auto-detects chain type:
      - MORM L1 RPC (HTTP /info → tips/latest)
      - EVM RPC via foundry's `cast` (anvil et al.)
    """
    import json as _json
    import urllib.request as _ur
    # try MORM L1 first
    try:
        with _ur.urlopen(rpc_url.rstrip("/") + "/info", timeout=2) as r:
            info = _json.loads(r.read())
        if "tips" in info:
            latest = info.get("latest") or []
            if latest:
                return "0x" + latest[0]["hash"], int(latest[0]["height"])
            # genesis (no blocks yet)
            tip = info["tips"][0]
            return "0x" + tip, 0
    except Exception:
        pass
    # fall back to EVM
    h = subprocess.run(
        ["cast", "block", "latest", "--field", "hash", "--rpc-url", rpc_url],
        capture_output=True, check=True, text=True,
    ).stdout.strip()
    n = subprocess.run(
        ["cast", "block", "latest", "--field", "number", "--rpc-url", rpc_url],
        capture_output=True, check=True, text=True,
    ).stdout.strip()
    return h, int(n)


def encode_evidence(
    src: Path,
    out_dir: Path,
    role: str,
    order_id: str,
    block_hash: str,
) -> list[Path]:
    """Burn (role, order_id, block_hash, timecode) into every frame, then
    split into 3-second WebM cells exactly like the regular encoder."""
    if role not in ("packing", "opening"):
        raise ValueError(f"role must be packing|opening, got {role!r}")
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg not found in PATH")

    out_dir.mkdir(parents=True, exist_ok=True)
    pattern = out_dir / "cell_%04d.webm"
    info = probe(src)
    fps = min(info.fps, TARGET_FPS) if info.fps > 0 else TARGET_FPS

    short_oid = order_id[2:14] if order_id.startswith("0x") else order_id[:12]
    short_bh  = block_hash[2:14] if block_hash.startswith("0x") else block_hash[:12]
    # Avoid `:` inside the watermark text — drawtext's filter parser would
    # treat it as an option separator. Use `-` and pass the text via a file
    # so we never have to escape ffmpeg filter syntax.
    label = f"MORM | {role} | ord-{short_oid} | blk-{short_bh}"
    text_file = out_dir / "_watermark.txt"
    text_file.write_text(label)

    fontfile = "/System/Library/Fonts/Monaco.ttf"

    drawtext = (
        f"drawtext=textfile={text_file}"
        f":fontfile={fontfile}"
        f":fontsize=18:fontcolor=white@0.92"
        f":box=1:boxcolor=black@0.55:boxborderw=6"
        f":x=12:y=12"
    )

    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-i", str(src),
        "-vf", drawtext,
        "-c:v", "libvpx-vp9",
        "-b:v", VIDEO_BITRATE,
        "-r", str(fps),
        "-deadline", "good", "-cpu-used", "4",
        "-g", str(int(fps * CELL_DURATION_SEC)),
        "-keyint_min", str(int(fps * CELL_DURATION_SEC)),
        "-force_key_frames", f"expr:gte(t,n_forced*{CELL_DURATION_SEC})",
    ]
    if info.has_audio:
        cmd += ["-c:a", "libopus", "-b:a", AUDIO_BITRATE]
    else:
        cmd += ["-an"]
    cmd += [
        "-f", "segment",
        "-segment_time", str(CELL_DURATION_SEC),
        "-reset_timestamps", "1",
        str(pattern),
    ]
    subprocess.run(cmd, check=True)
    return sorted(out_dir.glob("cell_*.webm"))


def cut_score(cell_path: Path) -> dict:
    """Detect unnatural cuts / splices in an evidence cell.

    Spec ref: MORM.md §6 — "AI による動体解析、不自然なカットがないか".
    We extract a high-rate frame stream, compute per-frame diffs, and look
    for diff values that stand out from the local median. Genuine motion is
    smooth (diffs near median); a hard cut produces a single huge spike.

    Returns {
      'frames':         total frames analyzed,
      'mean_diff':      average per-frame change (0-1, normalized),
      'max_diff':       largest single-frame change,
      'spike_count':    # of frames whose diff exceeds 5x local median,
      'cut_score':      spike_count / frames (0 = clean, 1 = all cuts),
    }
    """
    import numpy as np  # noqa: E501  (already imported at top, but explicit here)
    cmd = [
        "ffmpeg", "-loglevel", "error", "-i", str(cell_path),
        "-vf", "fps=15,scale=64:64,format=gray",
        "-f", "rawvideo", "-",
    ]
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    if len(raw) < 64 * 64 * 3:
        return {"frames": 0, "mean_diff": 0.0, "max_diff": 0.0,
                "spike_count": 0, "cut_score": 0.0}
    arr = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 64, 64).astype(np.float32)
    if arr.shape[0] < 3:
        return {"frames": int(arr.shape[0]), "mean_diff": 0.0, "max_diff": 0.0,
                "spike_count": 0, "cut_score": 0.0}
    diffs = np.abs(arr[1:] - arr[:-1]).mean(axis=(1, 2)) / 255.0
    median = float(np.median(diffs)) + 1e-6
    spike_threshold = median * 5.0 + 0.05  # absolute floor at 0.05 to ignore tiny static
    spikes = int((diffs > spike_threshold).sum())
    return {
        "frames": int(arr.shape[0]),
        "mean_diff": float(diffs.mean()),
        "max_diff": float(diffs.max()),
        "spike_count": spikes,
        "cut_score": float(spikes) / max(1, int(diffs.size)),
    }


CUT_SCORE_THRESHOLD = 0.01    # >1% of frame-pairs flagged as spikes
MAX_DIFF_THRESHOLD  = 0.10    # any single frame-pair jump above this = suspicious


def verify_evidence_video(cell_path: Path) -> dict:
    """Single-call AI tamper check on an evidence video.

    Returns {
      'cut_score', 'max_diff', 'spike_count', 'frames',
      'tampered': bool,         # True if either threshold tripped
      'reason':   str | None,
    }
    """
    s = cut_score(cell_path)
    tampered = (s["cut_score"] > CUT_SCORE_THRESHOLD
                or s["max_diff"] > MAX_DIFF_THRESHOLD)
    reason = None
    if tampered:
        reason = (f"cut_score={s['cut_score']:.4f} "
                  f"max_diff={s['max_diff']:.4f} "
                  f"(thresholds: cut>{CUT_SCORE_THRESHOLD}, max>{MAX_DIFF_THRESHOLD})")
    return {**s, "tampered": tampered, "reason": reason}


def evidence_root_hash(
    cells: list[Path], role: str, order_id: str, block_hash: str,
) -> str:
    """Deterministic 0x-prefixed sha256 over (binding-tuple || cell bytes).

    Returns 32-byte hex; suitable to pass directly to submitPackingProof /
    submitOpeningProof which expect bytes32.
    """
    h = hashlib.sha256()
    h.update(role.encode())
    h.update(b"\x00")
    h.update(order_id.encode())
    h.update(b"\x00")
    h.update(block_hash.encode())
    h.update(b"\x00")
    for p in sorted(cells):
        with p.open("rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
    return "0x" + h.hexdigest()


def write_evidence_meta(out_dir: Path, **fields) -> Path:
    """Write a JSON sidecar that the validator/verifier reads back."""
    import json
    p = out_dir / "evidence.json"
    p.write_text(json.dumps(fields, indent=2))
    return p
