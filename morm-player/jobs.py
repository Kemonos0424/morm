"""Phase 25Vb in-process job queue for HLS encoding.

Spec §4 25Vb suggests Redis + RQ. For PoC we use a ThreadPoolExecutor with
an in-memory status dict — no external broker required, single-process
scope. The status dict is exposed via /api/video/<cid>/status; the worker
function runs `morm-core hls-encode` in a subprocess and updates the dict.
"""
from __future__ import annotations

import secrets
import shutil
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class JobStatus:
    job_id: str
    state: str            # "queued", "encoding", "done", "error"
    content_id: str | None = None
    started_at: float | None = None
    finished_at: float | None = None
    error: str | None = None
    bytes_in: int = 0
    files_out: int = 0
    log_tail: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "job_id": self.job_id,
            "state": self.state,
            "content_id": self.content_id,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "error": self.error,
            "bytes_in": self.bytes_in,
            "files_out": self.files_out,
            "log_tail": self.log_tail[-20:],
        }


class JobRegistry:
    """Thread-safe map of job_id → JobStatus, plus content_id → job_id index.

    `post_encode_hook` is an optional callable `(JobStatus, manifest_path)`
    invoked after a successful encode but before the job is marked done.
    Used by Phase 25Va-finish to register the new content_id on-chain via
    a treasury REGISTER_CONTENT tx. Hook errors are recorded in log_tail
    but do not flip the job state to error — the encode itself succeeded
    and the file pack is usable; the chain registration is a side effect.
    """

    def __init__(self, max_workers: int = 1, post_encode_hook=None):
        self._lock = threading.Lock()
        self._jobs: dict[str, JobStatus] = {}
        self._cid_to_job: dict[str, str] = {}
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers, thread_name_prefix="morm-encode-")
        self._post_encode_hook = post_encode_hook

    @staticmethod
    def _gen_id() -> str:
        return secrets.token_hex(8)

    def submit_encode(
        self,
        *,
        src_path: Path,
        out_root: Path,
        morm_core_python: str,
        morm_core_dir: Path,
        bytes_in: int,
    ) -> JobStatus:
        job_id = self._gen_id()
        st = JobStatus(job_id=job_id, state="queued", bytes_in=bytes_in)
        with self._lock:
            self._jobs[job_id] = st
        self._executor.submit(
            self._run_encode, st, src_path, out_root,
            morm_core_python, morm_core_dir,
        )
        return st

    def get(self, job_id: str) -> JobStatus | None:
        with self._lock:
            return self._jobs.get(job_id)

    def get_by_content_id(self, content_id: str) -> JobStatus | None:
        with self._lock:
            jid = self._cid_to_job.get(content_id)
            return self._jobs.get(jid) if jid else None

    def list_recent(self, limit: int = 20) -> list[JobStatus]:
        with self._lock:
            jobs = list(self._jobs.values())
        jobs.sort(key=lambda j: j.started_at or 0, reverse=True)
        return jobs[:limit]

    def _bind_content(self, job_id: str, content_id: str) -> None:
        with self._lock:
            self._cid_to_job[content_id] = job_id

    def _run_encode(
        self,
        st: JobStatus,
        src_path: Path,
        out_root: Path,
        morm_core_python: str,
        morm_core_dir: Path,
    ) -> None:
        st.started_at = time.time()
        st.state = "encoding"
        try:
            cmd = [morm_core_python, "-m", "morm_core.cli", "hls-encode",
                   str(src_path), "--out", str(out_root)]
            st.log_tail.append("$ " + " ".join(cmd))
            proc = subprocess.run(
                cmd, capture_output=True, text=True,
                cwd=str(morm_core_dir), timeout=600,
            )
            for line in proc.stdout.splitlines():
                st.log_tail.append(line)
            for line in proc.stderr.splitlines():
                st.log_tail.append(f"[stderr] {line}")
            if proc.returncode != 0:
                st.state = "error"
                st.error = (
                    f"encoder exited {proc.returncode}: "
                    f"{(proc.stderr or proc.stdout)[-500:]}"
                )
                return
            cid = (proc.stdout.strip().splitlines() or [""])[-1].strip()
            if not cid or len(cid) > 64:
                st.state = "error"
                st.error = f"bad content_id from encoder: {cid!r}"
                return
            st.content_id = cid
            self._bind_content(st.job_id, cid)
            target = (out_root / cid).resolve()
            st.files_out = sum(1 for p in target.rglob("*") if p.is_file())
            if self._post_encode_hook:
                try:
                    self._post_encode_hook(st, target / "manifest.json")
                except Exception as he:  # noqa: BLE001
                    st.log_tail.append(f"[post-hook] {type(he).__name__}: {he}")
            st.state = "done"
        except subprocess.TimeoutExpired:
            st.state = "error"
            st.error = "encoder timed out (>600s)"
        except Exception as e:  # noqa: BLE001
            st.state = "error"
            st.error = f"{type(e).__name__}: {e}"
        finally:
            st.finished_at = time.time()
            try:
                if src_path.exists():
                    src_path.unlink()
            except OSError:
                pass


__all__ = ["JobStatus", "JobRegistry"]
