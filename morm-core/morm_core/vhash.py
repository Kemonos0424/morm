"""V-Hash: perceptual fingerprint for a Cell.

Two channels:
- Visual: pHash over N keyframes (8x8 DCT-based perceptual hash, robust to
  resize/recompression/minor color shifts).
- Audio:  spectral fingerprint over the cell's audio track (rough beats/energy
  bands), 0 if no audio.

The hash is intentionally short and order-stable so identical/near-identical
cells collide on bitwise comparison or low Hamming distance.
"""
from __future__ import annotations

import io
import subprocess
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image

KEYFRAMES_PER_CELL = 6
PHASH_SIZE = 8  # → 64-bit per frame
AUDIO_BANDS = 32
AUDIO_FRAMES = 8


@dataclass
class VHash:
    visual: str          # hex, KEYFRAMES_PER_CELL * 16 chars
    visual_flipped: str  # same length — pHash of left-right-flipped frames
    audio: str           # hex, AUDIO_BANDS * AUDIO_FRAMES / 4 chars
    motion: float        # 0.0–1.0, mean inter-frame change. <0.02 = static slideshow

    def to_dict(self) -> dict:
        return {
            "visual": self.visual,
            "visual_flipped": self.visual_flipped,
            "audio": self.audio,
            "motion": self.motion,
        }


def _phash_64bit(img: Image.Image) -> int:
    """Standard 8x8 DCT pHash."""
    g = img.convert("L").resize((32, 32), Image.LANCZOS)
    arr = np.asarray(g, dtype=np.float32)
    dct = _dct2(arr)
    low = dct[:PHASH_SIZE, :PHASH_SIZE]
    med = np.median(low.flatten()[1:])  # skip DC
    bits = (low > med).flatten()
    h = 0
    for b in bits:
        h = (h << 1) | int(b)
    return h


def _dct2(a: np.ndarray) -> np.ndarray:
    """2D DCT-II via separable 1D transforms (numpy-only, no scipy dep)."""
    return _dct1(_dct1(a, axis=0), axis=1)


def _dct1(a: np.ndarray, axis: int) -> np.ndarray:
    n = a.shape[axis]
    k = np.arange(n)
    j = k.reshape(-1, 1)
    basis = np.cos(np.pi * (2 * j + 1) * k / (2 * n))
    return np.tensordot(a, basis, axes=([axis], [0])).swapaxes(-1, axis)


def _extract_keyframes(cell_path: Path) -> list[Image.Image]:
    """Pull KEYFRAMES_PER_CELL frames from the cell as PIL images."""
    cmd = [
        "ffmpeg", "-loglevel", "error", "-i", str(cell_path),
        "-vf", f"fps={KEYFRAMES_PER_CELL}/3,scale=128:128",
        "-vframes", str(KEYFRAMES_PER_CELL),
        "-f", "image2pipe", "-vcodec", "mjpeg", "-",
    ]
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    blobs = _split_mjpeg(raw)[:KEYFRAMES_PER_CELL]
    if not blobs:
        return []
    while len(blobs) < KEYFRAMES_PER_CELL:
        blobs.append(blobs[-1])
    return [Image.open(io.BytesIO(b)) for b in blobs]


def _phash_concat(images: list[Image.Image]) -> str:
    if not images:
        return "0" * (KEYFRAMES_PER_CELL * 16)
    return "".join(f"{_phash_64bit(img):016x}" for img in images)


def visual_phash(cell_path: Path) -> str:
    """Concatenated 64-bit pHash for KEYFRAMES_PER_CELL frames (canonical)."""
    return _phash_concat(_extract_keyframes(cell_path))


def visual_phash_flipped(cell_path: Path) -> str:
    """Same as visual_phash but on each frame mirrored left-to-right.

    A horizontal-flip attack makes a copy bit-different from the canonical
    pHash, but storing the flipped pHash too lets the screener match either
    orientation in a single Hamming-distance comparison.
    """
    frames = _extract_keyframes(cell_path)
    if not frames:
        return "0" * (KEYFRAMES_PER_CELL * 16)
    flipped = [img.transpose(Image.FLIP_LEFT_RIGHT) for img in frames]
    return _phash_concat(flipped)


def motion_score(cell_path: Path) -> float:
    """Mean per-pixel intensity change between consecutive frames, in [0,1].

    Static slideshows / image-loops sit very low (≪ 0.01); real recorded
    motion is typically > 0.05. The screener uses this as a "Tempest-style"
    sanity check (MORM.md §5).
    """
    cmd = [
        "ffmpeg", "-loglevel", "error", "-i", str(cell_path),
        "-vf", "fps=10,scale=64:64,format=gray",
        "-f", "rawvideo", "-",
    ]
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    if len(raw) < 64 * 64 * 2:
        return 0.0
    arr = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 64, 64).astype(np.float32)
    if arr.shape[0] < 2:
        return 0.0
    diffs = np.abs(arr[1:] - arr[:-1])
    return float(diffs.mean()) / 255.0


def _split_mjpeg(blob: bytes) -> list[bytes]:
    """Split a concatenated MJPEG stream into individual JPEG payloads."""
    soi = b"\xff\xd8"
    eoi = b"\xff\xd9"
    out, i = [], 0
    while True:
        s = blob.find(soi, i)
        if s < 0:
            break
        e = blob.find(eoi, s)
        if e < 0:
            break
        out.append(blob[s:e + 2])
        i = e + 2
    return out


def audio_fingerprint(cell_path: Path) -> str:
    """Coarse spectral signature: AUDIO_BANDS bands × AUDIO_FRAMES windows.

    Returns a binary fingerprint encoded as hex. Returns all-zero if the cell
    has no audio stream or the decode produces an empty buffer.
    """
    sample_rate = 16000
    cmd = [
        "ffmpeg", "-loglevel", "error", "-i", str(cell_path),
        "-ac", "1", "-ar", str(sample_rate),
        "-f", "f32le", "-",
    ]
    res = subprocess.run(cmd, capture_output=True)
    if res.returncode != 0 or not res.stdout:
        return "0" * (AUDIO_BANDS * AUDIO_FRAMES // 4)
    samples = np.frombuffer(res.stdout, dtype=np.float32)
    if samples.size < AUDIO_FRAMES * 256:
        return "0" * (AUDIO_BANDS * AUDIO_FRAMES // 4)

    win = samples.size // AUDIO_FRAMES
    bits = []
    prev = None
    for f in range(AUDIO_FRAMES):
        chunk = samples[f * win:(f + 1) * win]
        spectrum = np.abs(np.fft.rfft(chunk))
        # pool into AUDIO_BANDS log-spaced bins
        edges = np.geomspace(1, len(spectrum), AUDIO_BANDS + 1).astype(int)
        edges[0] = 0
        bands = np.array([spectrum[edges[i]:edges[i + 1]].sum() for i in range(AUDIO_BANDS)])
        if prev is None:
            bits.extend([0] * AUDIO_BANDS)
        else:
            diff = bands - prev
            bits.extend((diff > 0).astype(int).tolist())
        prev = bands

    n = 0
    for b in bits:
        n = (n << 1) | b
    width = AUDIO_BANDS * AUDIO_FRAMES // 4
    return f"{n:0{width}x}"


def vhash(cell_path: Path) -> VHash:
    frames = _extract_keyframes(cell_path)
    flipped = [img.transpose(Image.FLIP_LEFT_RIGHT) for img in frames] if frames else []
    return VHash(
        visual=_phash_concat(frames),
        visual_flipped=_phash_concat(flipped),
        audio=audio_fingerprint(cell_path),
        motion=motion_score(cell_path),
    )


def hamming_hex(a: str, b: str) -> int:
    """Bitwise Hamming distance between two equal-length hex strings."""
    if len(a) != len(b):
        raise ValueError("hash length mismatch")
    return bin(int(a, 16) ^ int(b, 16)).count("1")
