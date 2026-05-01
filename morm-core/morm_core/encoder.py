"""Encode source video into 3-second WebM cells (VP9, ≤30fps).

Spec ref: MORM.md §3, §7. Each cell is independently decodable so the
50%/10% player can stream and discard segments without referencing peers.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

CELL_DURATION_SEC = 3
TARGET_FPS = 30
VIDEO_BITRATE = "1200k"
AUDIO_BITRATE = "96k"


@dataclass
class ProbeResult:
    duration: float
    width: int
    height: int
    fps: float
    has_audio: bool


def probe(path: Path) -> ProbeResult:
    cmd = [
        "ffprobe", "-v", "error", "-print_format", "json",
        "-show_streams", "-show_format", str(path),
    ]
    out = subprocess.run(cmd, capture_output=True, check=True, text=True).stdout
    data = json.loads(out)
    v = next(s for s in data["streams"] if s["codec_type"] == "video")
    has_audio = any(s["codec_type"] == "audio" for s in data["streams"])
    num, den = (int(x) for x in v["r_frame_rate"].split("/"))
    fps = num / den if den else 0.0
    return ProbeResult(
        duration=float(data["format"]["duration"]),
        width=int(v["width"]),
        height=int(v["height"]),
        fps=fps,
        has_audio=has_audio,
    )


def encode_cells(src: Path, out_dir: Path) -> list[Path]:
    """Split src into independently-decodable VP9/WebM cells of CELL_DURATION_SEC."""
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg not found in PATH")
    out_dir.mkdir(parents=True, exist_ok=True)
    pattern = out_dir / "cell_%04d.webm"

    info = probe(src)
    fps = min(info.fps, TARGET_FPS) if info.fps > 0 else TARGET_FPS

    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-i", str(src),
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
