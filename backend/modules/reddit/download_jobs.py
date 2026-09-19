"""Transient progress registry for confirmed Reddit media downloads."""
from __future__ import annotations

from collections import OrderedDict
from copy import deepcopy
from datetime import datetime, timezone
from threading import RLock, Thread
from typing import Any, Callable
from uuid import uuid4


JobRunner = Callable[[Callable[[dict[str, Any]], None]], dict[str, Any]]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class RedditDownloadJobError(RuntimeError):
    pass


class RedditDownloadJobs:
    """Run one confirmed transfer while keeping UI-readable progress."""

    def __init__(self, *, history_limit: int = 25) -> None:
        self._lock = RLock()
        self._jobs: OrderedDict[str, dict[str, Any]] = OrderedDict()
        self._active_job_id: str | None = None
        self._history_limit = history_limit

    def start(
        self,
        *,
        target_kind: str,
        target_id: str,
        planned: int,
        runner: JobRunner,
    ) -> dict[str, Any]:
        with self._lock:
            if self._active_job_id is not None:
                raise RedditDownloadJobError(
                    "Another Reddit media download is already running"
                )
            job_id = uuid4().hex
            created_at = _now()
            job = {
                "job_id": job_id,
                "target_kind": target_kind,
                "target_id": target_id,
                "status": "queued",
                "phase": "queued",
                "progress": 0.0,
                "planned": planned,
                "attempted": 0,
                "completed": 0,
                "failed": 0,
                "bytes_acquired": 0,
                "error": None,
                "result": None,
                "created_at": created_at,
                "updated_at": created_at,
            }
            self._jobs[job_id] = job
            self._active_job_id = job_id
            while len(self._jobs) > self._history_limit:
                self._jobs.popitem(last=False)
            thread = Thread(
                target=self._run,
                args=(job_id, runner),
                daemon=True,
                name=f"reddit-media-{job_id[:8]}",
            )
            thread.start()
            return deepcopy(job)

    def _run(self, job_id: str, runner: JobRunner) -> None:
        self._update(job_id, status="running", phase="starting")

        def progress(values: dict[str, Any]) -> None:
            planned = max(int(values.get("planned") or 0), 0)
            completed = max(int(values.get("completed") or 0), 0)
            failed = max(int(values.get("failed") or 0), 0)
            done = completed + failed
            self._update(
                job_id,
                phase=str(values.get("phase") or "downloading"),
                progress=min(done / planned, 1.0) if planned else 0.0,
                planned=planned,
                attempted=max(int(values.get("attempted") or 0), 0),
                completed=completed,
                failed=failed,
                bytes_acquired=max(
                    int(values.get("bytes_acquired") or 0), 0
                ),
            )

        try:
            result = runner(progress)
            download = result.get("download", {})
            planned = max(int(download.get("planned") or 0), 0)
            completed = max(int(download.get("completed") or 0), 0)
            failed = max(int(download.get("failed") or 0), 0)
            self._update(
                job_id,
                status="completed" if failed == 0 else "completed_with_errors",
                phase="completed",
                progress=1.0,
                planned=planned,
                attempted=max(int(download.get("attempted") or 0), 0),
                completed=completed,
                failed=failed,
                bytes_acquired=max(
                    int(download.get("bytes_acquired") or 0), 0
                ),
                result=result,
            )
        except Exception as exc:
            self._update(
                job_id,
                status="failed",
                phase="failed",
                error=str(exc)[-2000:],
            )
        finally:
            with self._lock:
                if self._active_job_id == job_id:
                    self._active_job_id = None

    def _update(self, job_id: str, **values: Any) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            job.update(values)
            job["updated_at"] = _now()

    def job(self, job_id: str) -> dict[str, Any]:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise RedditDownloadJobError("Unknown Reddit media job")
            return deepcopy(job)

    def jobs(self) -> list[dict[str, Any]]:
        with self._lock:
            return [
                deepcopy(value)
                for value in reversed(self._jobs.values())
            ]

    def busy(self) -> bool:
        with self._lock:
            return self._active_job_id is not None
