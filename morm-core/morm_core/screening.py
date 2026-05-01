"""Screening DB: V-Hash registry, duplicate detection, timestamp-race admission.

Implements MORM.md §5 ("初期値絶対主義"):
  - the *first* submission to be committed wins; later duplicates are rejected;
  - cells that lose the race are flagged for garbage collection;
  - generation_id (AI provenance) is a hard unique key.

Cell-level matching catches re-encodes, resolution changes, and partial
clip-outs: if ≥ MATCH_RATIO of a submission's cells collide with an existing
content, the whole submission is rejected.
"""
from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path

from .vhash import hamming_hex

VISUAL_DIST_THRESHOLD = 30   # /384 bits
AUDIO_DIST_THRESHOLD = 32    # /256 bits
MATCH_RATIO = 0.5            # ≥ 50% of cells matching → duplicate
MOTION_FAKE_THRESHOLD = 0.005  # mean cell motion below this → "static slideshow"

SCHEMA = """
CREATE TABLE IF NOT EXISTS contents (
    content_id     TEXT PRIMARY KEY,
    creator_id     TEXT NOT NULL,
    generation_id  TEXT,
    root_hash      TEXT NOT NULL,
    status         TEXT NOT NULL,             -- accepted | rejected
    rejection_reason TEXT,
    duplicate_of   TEXT,                      -- content_id of the winner
    submitted_at   REAL NOT NULL,
    accepted_at    REAL,
    cells_dir      TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_generation_id_accepted
    ON contents(generation_id) WHERE generation_id IS NOT NULL AND status = 'accepted';

CREATE TABLE IF NOT EXISTS cells (
    cell_pk        INTEGER PRIMARY KEY AUTOINCREMENT,
    content_id     TEXT NOT NULL REFERENCES contents(content_id),
    cell_index     INTEGER NOT NULL,
    sha256         TEXT NOT NULL,
    visual_phash   TEXT NOT NULL,
    visual_flipped TEXT NOT NULL DEFAULT '',
    audio_fp       TEXT NOT NULL,
    motion         REAL NOT NULL DEFAULT 0.0,
    UNIQUE(content_id, cell_index)
);
CREATE INDEX IF NOT EXISTS idx_cells_content ON cells(content_id);
CREATE INDEX IF NOT EXISTS idx_cells_sha     ON cells(sha256);
"""


@dataclass
class ScreenResult:
    accepted: bool
    content_id: str
    reason: str | None = None
    duplicate_of: str | None = None
    matched_cells: int = 0
    total_cells: int = 0


def open_db(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, isolation_level=None)  # we manage tx explicitly
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(SCHEMA)
    return conn


def _is_silent(audio_fp: str) -> bool:
    return all(c == "0" for c in audio_fp)


def _visual_match(a_v: str, a_vf: str, b_v: str, b_vf: str) -> bool:
    """True if a-canonical or a-flipped matches b-canonical (any orientation)."""
    if hamming_hex(a_v, b_v) <= VISUAL_DIST_THRESHOLD:
        return True
    if a_vf and hamming_hex(a_vf, b_v) <= VISUAL_DIST_THRESHOLD:
        return True   # uploader's content is the flipped version of an original
    if b_vf and hamming_hex(a_v, b_vf) <= VISUAL_DIST_THRESHOLD:
        return True   # uploader's content is the original of an existing flipped record
    return False


def _cell_matches(a_visual: str, a_visual_flipped: str, a_audio: str,
                  b_visual: str, b_visual_flipped: str, b_audio: str) -> bool:
    if not _visual_match(a_visual, a_visual_flipped, b_visual, b_visual_flipped):
        return False
    if _is_silent(a_audio) or _is_silent(b_audio):
        return True
    return hamming_hex(a_audio, b_audio) <= AUDIO_DIST_THRESHOLD


def _check_motion_fake(manifest: dict) -> tuple[bool, float]:
    """Return (is_fake, mean_motion). Mean motion across cells must exceed
    MOTION_FAKE_THRESHOLD; otherwise treat as static-image slideshow."""
    cells = manifest.get("cells", [])
    if not cells:
        return False, 0.0
    motions = [c["vhash"].get("motion", 0.0) for c in cells]
    mean = sum(motions) / len(motions)
    return mean < MOTION_FAKE_THRESHOLD, mean


def _find_duplicate(conn: sqlite3.Connection, manifest: dict) -> tuple[str | None, int]:
    """Return (existing_content_id, matched_cell_count) or (None, 0)."""
    new_cells = manifest["cells"]
    if not new_cells:
        return None, 0

    rows = conn.execute(
        "SELECT c.content_id, c.visual_phash, c.visual_flipped, c.audio_fp "
        "FROM cells c JOIN contents ct ON c.content_id = ct.content_id "
        "WHERE ct.status = 'accepted'"
    ).fetchall()

    by_content: dict[str, list[tuple[str, str, str]]] = {}
    for cid, vp, vpf, afp in rows:
        by_content.setdefault(cid, []).append((vp, vpf, afp))

    needed = max(1, int(len(new_cells) * MATCH_RATIO + 0.5))

    for cid, existing in by_content.items():
        matched = 0
        for nc in new_cells:
            nv = nc["vhash"]["visual"]
            nvf = nc["vhash"].get("visual_flipped", "")
            na = nc["vhash"]["audio"]
            for ev, evf, ea in existing:
                if _cell_matches(nv, nvf, na, ev, evf, ea):
                    matched += 1
                    break
        if matched >= needed:
            return cid, matched
    return None, 0


def screen(
    conn: sqlite3.Connection,
    manifest_path: Path,
    cells_dir: Path | None = None,
) -> ScreenResult:
    """Submit a manifest. Atomic: timestamp-race resolved by SQLite write order."""
    manifest = json.loads(manifest_path.read_text())
    cid = manifest["content_id"]
    gen_id = manifest.get("generation_id")
    creator = manifest["creator_id"]

    now = time.time()
    cur = conn.cursor()
    cur.execute("BEGIN IMMEDIATE")
    try:
        # 1. exact content_id collision (same upload submitted twice)
        existing = cur.execute(
            "SELECT status FROM contents WHERE content_id = ?", (cid,)
        ).fetchone()
        if existing:
            cur.execute("COMMIT")
            return ScreenResult(False, cid, reason=f"already-submitted ({existing[0]})")

        # 2. generation_id collision — AI provenance is unique by definition
        if gen_id:
            row = cur.execute(
                "SELECT content_id FROM contents WHERE generation_id = ? AND status = 'accepted'",
                (gen_id,),
            ).fetchone()
            if row:
                cur.execute(
                    "INSERT INTO contents (content_id, creator_id, generation_id, root_hash, "
                    "status, rejection_reason, duplicate_of, submitted_at, cells_dir) "
                    "VALUES (?, ?, ?, ?, 'rejected', 'generation-id-collision', ?, ?, ?)",
                    (cid, creator, gen_id, "", row[0], now, str(cells_dir) if cells_dir else None),
                )
                cur.execute("COMMIT")
                return ScreenResult(False, cid, reason="generation-id-collision",
                                    duplicate_of=row[0])

        # 3a. motion sanity check (Tempest-style: reject static-image slideshows)
        is_fake, mean_motion = _check_motion_fake(manifest)
        if is_fake:
            cur.execute(
                "INSERT INTO contents (content_id, creator_id, generation_id, root_hash, "
                "status, rejection_reason, duplicate_of, submitted_at, cells_dir) "
                "VALUES (?, ?, ?, ?, 'rejected', ?, NULL, ?, ?)",
                (cid, creator, gen_id, "",
                 f"low-motion-fake (mean={mean_motion:.4f})",
                 now, str(cells_dir) if cells_dir else None),
            )
            cur.execute("COMMIT")
            return ScreenResult(False, cid,
                                reason=f"low-motion-fake (mean={mean_motion:.4f})",
                                total_cells=len(manifest["cells"]))

        # 3a'. AI tamper / splice detection (Phase 15c, screening-pipeline
        # integrated). Walk every cell file; if any cell trips the cut_score
        # or max_diff threshold the whole submission is rejected.
        if cells_dir:
            from .evidence import verify_evidence_video
            for nc in manifest["cells"]:
                cell_path = Path(cells_dir) / nc["filename"]
                if not cell_path.exists():
                    continue
                try:
                    v = verify_evidence_video(cell_path)
                except Exception:
                    continue
                if v.get("tampered"):
                    msg = f"tampered-video cell={nc['index']} {v.get('reason','?')}"
                    cur.execute(
                        "INSERT INTO contents (content_id, creator_id, generation_id, root_hash, "
                        "status, rejection_reason, duplicate_of, submitted_at, cells_dir) "
                        "VALUES (?, ?, ?, ?, 'rejected', ?, NULL, ?, ?)",
                        (cid, creator, gen_id, "", msg, now,
                         str(cells_dir) if cells_dir else None),
                    )
                    cur.execute("COMMIT")
                    return ScreenResult(False, cid, reason=msg,
                                        total_cells=len(manifest["cells"]))

        # 3b. perceptual duplicate scan (canonical OR flipped)
        dup_of, matched = _find_duplicate(conn, manifest)
        if dup_of:
            cur.execute(
                "INSERT INTO contents (content_id, creator_id, generation_id, root_hash, "
                "status, rejection_reason, duplicate_of, submitted_at, cells_dir) "
                "VALUES (?, ?, ?, ?, 'rejected', 'perceptual-duplicate', ?, ?, ?)",
                (cid, creator, gen_id, "", dup_of, now,
                 str(cells_dir) if cells_dir else None),
            )
            cur.execute("COMMIT")
            return ScreenResult(False, cid, reason="perceptual-duplicate",
                                duplicate_of=dup_of, matched_cells=matched,
                                total_cells=len(manifest["cells"]))

        # 4. accepted — register content + cells
        cur.execute(
            "INSERT INTO contents (content_id, creator_id, generation_id, root_hash, "
            "status, submitted_at, accepted_at, cells_dir) "
            "VALUES (?, ?, ?, ?, 'accepted', ?, ?, ?)",
            (cid, creator, gen_id, "", now, now,
             str(cells_dir) if cells_dir else None),
        )
        for c in manifest["cells"]:
            cur.execute(
                "INSERT INTO cells (content_id, cell_index, sha256, visual_phash, "
                "visual_flipped, audio_fp, motion) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (cid, c["index"], c["sha256"],
                 c["vhash"]["visual"],
                 c["vhash"].get("visual_flipped", ""),
                 c["vhash"]["audio"],
                 c["vhash"].get("motion", 0.0)),
            )
        cur.execute("COMMIT")
        return ScreenResult(True, cid, total_cells=len(manifest["cells"]))
    except Exception:
        cur.execute("ROLLBACK")
        raise


def gc_rejected(conn: sqlite3.Connection, dry_run: bool = False) -> list[Path]:
    """Sweep rejected submissions' cell directories — the '一斉消去' enforcement.

    Returns the list of paths that were (or would be, if dry_run) deleted.
    """
    import shutil

    rows = conn.execute(
        "SELECT content_id, cells_dir FROM contents "
        "WHERE status = 'rejected' AND cells_dir IS NOT NULL"
    ).fetchall()
    deleted: list[Path] = []
    for _cid, cells_dir in rows:
        p = Path(cells_dir)
        if p.exists():
            deleted.append(p)
            if not dry_run:
                shutil.rmtree(p, ignore_errors=True)
    return deleted


def stats(conn: sqlite3.Connection) -> dict:
    cur = conn.cursor()
    accepted = cur.execute(
        "SELECT COUNT(*) FROM contents WHERE status='accepted'"
    ).fetchone()[0]
    rejected = cur.execute(
        "SELECT COUNT(*) FROM contents WHERE status='rejected'"
    ).fetchone()[0]
    cells = cur.execute("SELECT COUNT(*) FROM cells").fetchone()[0]
    return {"accepted": accepted, "rejected": rejected, "registered_cells": cells}
