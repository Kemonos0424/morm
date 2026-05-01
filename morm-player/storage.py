"""Phase 25Vb storage abstraction.

Selects between local FS and S3-compatible (R2 / B2 / MinIO) via the
`MORM_STORAGE_BACKEND` env var. The S3 backend uses boto3 lazily — it is
imported only when actually selected, so the FS path has no extra deps.

Public API (sufficient for both encoder output and playback serving):

    backend = StorageBackend.from_env(default_root=Path(...))
    backend.put_dir(local_dir, key_prefix)       # upload an entire dir
    backend.open_read(key) -> file-like          # streamed read
    path = backend.local_path(key)               # FS only; None for S3
    backend.exists(key) -> bool
    backend.list_prefixes(prefix) -> list[str]   # 1-level subdirs

For 25Vb we keep the FS backend as the default (`fs`). The S3 wrapper is
implemented but only smoke-tested where boto3 + bucket are available.
"""
from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path


@dataclass
class StorageBackend:
    """Common interface; the actual implementation is selected at __init__."""

    backend: str          # "fs" or "s3"
    root: Path | None     # FS root (None for s3)
    bucket: str | None    # S3 bucket (None for fs)
    s3_client: object | None = None
    s3_endpoint: str | None = None

    @classmethod
    def from_env(cls, default_root: Path) -> "StorageBackend":
        backend = os.environ.get("MORM_STORAGE_BACKEND", "fs").lower()
        if backend == "fs":
            default_root.mkdir(parents=True, exist_ok=True)
            return cls(backend="fs", root=default_root, bucket=None)
        if backend == "s3":
            try:
                import boto3  # type: ignore
            except ImportError as e:
                raise RuntimeError(
                    "MORM_STORAGE_BACKEND=s3 but boto3 is not installed. "
                    "pip install boto3"
                ) from e
            bucket = os.environ.get("MORM_S3_BUCKET")
            endpoint = os.environ.get("MORM_S3_ENDPOINT")  # R2/B2 custom url
            if not bucket:
                raise RuntimeError("MORM_STORAGE_BACKEND=s3 requires MORM_S3_BUCKET")
            kwargs = {}
            if endpoint:
                kwargs["endpoint_url"] = endpoint
            client = boto3.client("s3", **kwargs)
            return cls(backend="s3", root=None, bucket=bucket,
                       s3_client=client, s3_endpoint=endpoint)
        raise RuntimeError(f"unknown MORM_STORAGE_BACKEND={backend!r}")

    # ---- write ----------------------------------------------------------
    def put_dir(self, local_dir: Path, key_prefix: str) -> int:
        """Copy / upload an entire local dir under <storage>/<key_prefix>/.
        Returns number of files written."""
        if self.backend == "fs":
            target = (self.root / key_prefix).resolve()
            assert self.root is not None
            assert str(target).startswith(str(self.root.resolve()))
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(local_dir, target)
            return sum(1 for _ in target.rglob("*") if _.is_file())
        # s3
        n = 0
        for p in local_dir.rglob("*"):
            if not p.is_file():
                continue
            rel = p.relative_to(local_dir).as_posix()
            self.s3_client.upload_file(  # type: ignore[union-attr]
                str(p), self.bucket,
                f"{key_prefix.rstrip('/')}/{rel}",
            )
            n += 1
        return n

    # ---- read -----------------------------------------------------------
    def local_path(self, key: str) -> Path | None:
        """Return a filesystem path for the FS backend; None for s3."""
        if self.backend != "fs" or self.root is None:
            return None
        target = (self.root / key).resolve()
        if not str(target).startswith(str(self.root.resolve())):
            return None
        return target

    def exists(self, key: str) -> bool:
        if self.backend == "fs":
            p = self.local_path(key)
            return p is not None and p.exists()
        try:
            self.s3_client.head_object(Bucket=self.bucket, Key=key)  # type: ignore[union-attr]
            return True
        except Exception:
            return False

    def list_prefixes(self, prefix: str) -> list[str]:
        """List the immediate sub-directories (or sub-keys) under prefix."""
        if self.backend == "fs":
            base = self.local_path(prefix.rstrip("/"))
            if not base or not base.is_dir():
                return []
            return sorted(p.name for p in base.iterdir() if p.is_dir())
        # s3 — use Delimiter to enumerate "directories"
        out: list[str] = []
        kwargs = {"Bucket": self.bucket, "Prefix": prefix.rstrip("/") + "/",
                  "Delimiter": "/"}
        while True:
            resp = self.s3_client.list_objects_v2(**kwargs)  # type: ignore[union-attr]
            for cp in resp.get("CommonPrefixes", []):
                p = cp["Prefix"][len(kwargs["Prefix"]):].rstrip("/")
                if p:
                    out.append(p)
            if not resp.get("IsTruncated"):
                break
            kwargs["ContinuationToken"] = resp["NextContinuationToken"]
        return sorted(out)
