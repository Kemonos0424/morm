"""Cell manifest: the on-disk record an Edge Node serves and a Validator signs.

Spec ref: MORM.md §3 (MORM Cells), §5 (V-Hash), §7 (Generation ID).
The manifest is what eventually goes on-chain (or at least its root hash does).
"""
from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path

from . import __version__
from .vhash import VHash, vhash


def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for buf in iter(lambda: f.read(chunk), b""):
            h.update(buf)
    return h.hexdigest()


@dataclass
class CellRecord:
    index: int
    filename: str
    size: int
    sha256: str
    vhash: dict
    duration_target: float = 3.0


@dataclass
class ContentManifest:
    content_id: str
    creator_id: str
    generation_id: str | None
    created_at: int
    encoder_version: str
    cells: list[CellRecord] = field(default_factory=list)
    parent_block_hash: str | None = None  # latest MORM Chain block hash at encode time

    def to_json(self) -> str:
        d = asdict(self)
        return json.dumps(d, indent=2, ensure_ascii=False)

    @property
    def root_hash(self) -> str:
        """Deterministic hash of the cell list — this is what goes on-chain."""
        h = hashlib.sha256()
        h.update(self.content_id.encode())
        for c in self.cells:
            h.update(c.sha256.encode())
            h.update(c.vhash["visual"].encode())
            h.update(c.vhash["audio"].encode())
        return h.hexdigest()


def build_manifest(
    cells_dir: Path,
    creator_id: str,
    generation_id: str | None = None,
    parent_block_hash: str | None = None,
) -> ContentManifest:
    cell_files = sorted(cells_dir.glob("cell_*.webm"))
    records: list[CellRecord] = []
    for i, p in enumerate(cell_files):
        h = sha256_file(p)
        v: VHash = vhash(p)
        records.append(CellRecord(
            index=i,
            filename=p.name,
            size=p.stat().st_size,
            sha256=h,
            vhash=v.to_dict(),
        ))
    content_id = uuid.uuid4().hex if not records else hashlib.sha256(
        b"".join(r.sha256.encode() for r in records)
    ).hexdigest()
    return ContentManifest(
        content_id=content_id,
        creator_id=creator_id,
        generation_id=generation_id,
        created_at=int(time.time()),
        encoder_version=__version__,
        cells=records,
        parent_block_hash=parent_block_hash,
    )
