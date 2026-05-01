"""HLS/CMAF encoder for Phase 25Va.

Spec ref: ~/Desktop/MORM/docs/PHASE25-VIDEO.md §4 Phase 25Va.

Produces an ABR ladder (1080p/720p/480p/360p) of fMP4 segments under
`out_dir/<content_id>/` together with a master playlist:

    <content_id>/
      master.m3u8
      manifest.json
      1080p/  index.m3u8  init.mp4  seg_00001.<vhash16>.m4s ...
      720p/   ...
      480p/   ...
      360p/   ...

Per-segment V-Hash here is SHA256(file)[:16] (16 hex chars). The full V-Hash
recipe in vhash.py operates on a fully-decodable container; raw CMAF
fragments (.m4s) without their init.mp4 are not, so we use a content-hash
that is still tamper-evident and content-addressed. init.mp4 gets the same
SHA256 treatment per design §8 open question 3.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from .encoder import probe

# Bitrate ladder (video bps, audio bps, scale-W, scale-H, name).
# 4 rungs are enough for mobile + desktop testing. Order matters: the
# Phase 25-Video portrait pivot (2026-04-30): MORM is mobile-first and
# the player is a TikTok/Reels-style swipeable feed, so the encoder
# targets vertical 9:16 frames. The ladder names stay height-based
# (1080p/720p/...) — the height is the orientation-independent dimension
# that hls.js / ABR reasoning expects, and keeping the names lets every
# downstream `1080p/seg_*.m4s` URL keep working.
#
# Bitrates are unchanged from the landscape ladder because the pixel
# count at each rung is the same (1080×1920 = 1920×1080).
#
# Largest rung MUST be first so ffmpeg's split filter aligns with the
# var_stream_map order.
LADDER = [
    ("1080p", 1080, 1920, "5000k",  "192k"),
    ("720p",   720, 1280, "2500k",  "128k"),
    ("480p",   480,  854, "1000k",   "96k"),
    ("360p",   360,  640,  "600k",   "64k"),
]

HLS_SEG_DURATION_SEC = 3   # match Phase 1 cell granularity


@dataclass
class HLSManifest:
    content_id: str
    master_playlist_hash: str           # sha256 of master.m3u8 (hex)
    init_hashes: dict[str, str]         # resolution -> sha256(init.mp4)
    segments: dict[str, list[dict]] = field(default_factory=dict)
    # segments[resolution] = [{"index": int, "filename": str, "vhash": "16hex", "size": int}]

    def to_json(self) -> str:
        return json.dumps({
            "version": 1,
            "phase": "25Va",
            "content_id": self.content_id,
            "master_playlist_hash": self.master_playlist_hash,
            "init_hashes": self.init_hashes,
            "segments": self.segments,
        }, indent=2)


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(64 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _has_audio(src: Path) -> bool:
    try:
        return probe(src).has_audio
    except Exception:
        return False


def _build_ffmpeg_cmd(src: Path, out_dir: Path, with_audio: bool) -> list[str]:
    """Single-pass ABR HLS packaging command.

    Output layout (relative to out_dir):
        master.m3u8
        <name>/index.m3u8
        <name>/init.mp4
        <name>/seg_NNNNN.m4s
    """
    # 1) split + scale filters per rung. Portrait-only output (9:16):
    # `scale=w:h:force_original_aspect_ratio=increase` upscales the source
    # so both dimensions cover the target, then `crop=w:h` center-crops to
    # the exact rung size. This auto-handles three input shapes:
    #   - native 9:16 portrait → no-op fit
    #   - landscape (16:9) → height-bound scale + horizontal center crop
    #     (loses the left/right edges, which is the standard mobile feed
    #     UX for landscape sources)
    #   - square / arbitrary → fitted to 9:16 by whichever crop is smaller
    splits = "[0:v]split=" + str(len(LADDER)) + "".join(
        f"[v{i}]" for i in range(len(LADDER)))
    scales = ";".join(
        f"[v{i}]scale={w}:{h}:force_original_aspect_ratio=increase,"
        f"crop={w}:{h}[v{LADDER[i][0]}]"
        for i, (_name, w, h, _vb, _ab) in enumerate(LADDER)
    )
    fc = splits + ";" + scales

    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-i", str(src),
        "-filter_complex", fc,
    ]
    # 2) per-rung output spec
    var_map_parts = []
    for i, (name, _w, _h, vb, ab) in enumerate(LADDER):
        cmd += [
            "-map", f"[v{name}]",
            f"-c:v:{i}", "libx264",
            f"-b:v:{i}", vb,
            "-preset", "veryfast",
            "-g", str(HLS_SEG_DURATION_SEC * 30),
            "-keyint_min", str(HLS_SEG_DURATION_SEC * 30),
            "-sc_threshold", "0",
        ]
        if with_audio:
            cmd += [
                "-map", "a:0",
                f"-c:a:{i}", "aac",
                f"-b:a:{i}", ab,
                f"-ac:{i}", "2",
            ]
            var_map_parts.append(f"v:{i},a:{i},name:{name}")
        else:
            var_map_parts.append(f"v:{i},name:{name}")
    # 3) HLS muxer flags
    cmd += [
        "-f", "hls",
        "-hls_time", str(HLS_SEG_DURATION_SEC),
        "-hls_playlist_type", "vod",
        "-hls_segment_type", "fmp4",
        "-hls_flags", "independent_segments",
        "-hls_fmp4_init_filename", "init.mp4",
        "-hls_segment_filename",
        str(out_dir / "%v" / "seg_%05d.m4s"),
        "-master_pl_name", "master.m3u8",
        "-var_stream_map", " ".join(var_map_parts),
        str(out_dir / "%v" / "index.m3u8"),
    ]
    return cmd


def _rewrite_segments_with_vhash(
    out_dir: Path, resolution: str
) -> list[dict]:
    """Rename `seg_NNNNN.m4s` to `seg_NNNNN.<vhash16>.m4s` and patch the
    matching index.m3u8 to reference the new filenames."""
    rung_dir = out_dir / resolution
    index_path = rung_dir / "index.m3u8"
    text = index_path.read_text()

    segments: list[dict] = []
    for seg in sorted(rung_dir.glob("seg_*.m4s")):
        # skip already-renamed segments (idempotence)
        if seg.stem.count(".") >= 1:
            continue
        vhash16 = _sha256_file(seg)[:16]
        new_name = f"{seg.stem}.{vhash16}.m4s"
        new_path = rung_dir / new_name
        seg.rename(new_path)
        text = text.replace(seg.name, new_name)
        # parse the running segment number from "seg_00001"
        try:
            idx = int(seg.stem.split("_")[-1])
        except ValueError:
            idx = -1
        segments.append({
            "index": idx,
            "filename": new_name,
            "vhash": vhash16,
            "size": new_path.stat().st_size,
        })
    index_path.write_text(text)
    return sorted(segments, key=lambda s: s["index"])


def encode_hls(
    src: Path,
    out_dir: Path,
    content_id: str | None = None,
) -> HLSManifest:
    """Encode `src` into ABR HLS under `out_dir/<content_id>/`.

    `content_id` defaults to sha256 of source bytes (16 hex chars). The
    returned manifest is ALSO written as `<content_id>/manifest.json`."""
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg not found in PATH")
    src = src.resolve()
    if not src.exists():
        raise FileNotFoundError(src)

    if not content_id:
        content_id = _sha256_file(src)[:16]

    target_dir = (out_dir / content_id).resolve()
    target_dir.mkdir(parents=True, exist_ok=True)
    for rung in LADDER:
        (target_dir / rung[0]).mkdir(exist_ok=True)

    cmd = _build_ffmpeg_cmd(src, target_dir, with_audio=_has_audio(src))
    subprocess.run(cmd, check=True)

    init_hashes: dict[str, str] = {}
    segments: dict[str, list[dict]] = {}
    for name, _w, _h, _vb, _ab in LADDER:
        # ffmpeg names init segments init_<var_index>.mp4 even when
        # -hls_fmp4_init_filename is set (the flag is honored only when
        # there is a single variant). Capture whichever init the muxer
        # actually wrote; the playlist's EXT-X-MAP:URI references it.
        init_files = sorted((target_dir / name).glob("init*.mp4"))
        if init_files:
            init_hashes[name] = _sha256_file(init_files[0])
        segments[name] = _rewrite_segments_with_vhash(target_dir, name)

    master_path = target_dir / "master.m3u8"
    if not master_path.exists():
        raise RuntimeError(f"ffmpeg did not produce master.m3u8 in {target_dir}")
    manifest = HLSManifest(
        content_id=content_id,
        master_playlist_hash=_sha256_file(master_path),
        init_hashes=init_hashes,
        segments=segments,
    )
    (target_dir / "manifest.json").write_text(manifest.to_json())
    return manifest
