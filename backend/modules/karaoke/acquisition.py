"""Plan-confirm Kara.moe acquisition and resumable local jobs."""
from __future__ import annotations

from collections import deque
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import shutil
import threading
import time
from typing import Any, Callable
from uuid import uuid4

from module_descriptor import ModuleDescriptor
from modules.karaoke import catalog, kara_moe, lyrics, storage


DEFAULT_MAX_BYTES = 2 * 1024 * 1024 * 1024
PLAN_LIFETIME_MINUTES = 60
MIN_FREE_BYTES = 512 * 1024 * 1024


class KaraokeAcquisitionError(RuntimeError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _selection_sha(payload: dict[str, Any]) -> str:
    canonical = json.dumps(
        payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _language(record: dict[str, Any], normalized: dict[str, Any]) -> str:
    info = record.get("lyrics_infos") or record.get("lyricsInfos")
    if isinstance(info, dict):
        for key in ("language", "lang", "locale"):
            if info.get(key):
                return str(info[key])
    values = normalized.get("tags", {}).get("languages", [])
    return str(values[0]) if values else ""


def _require_free_space(path: Path, expected_bytes: int | None) -> None:
    available = shutil.disk_usage(path).free
    required = MIN_FREE_BYTES + max(int(expected_bytes or 0), 0)
    if available < required:
        raise KaraokeAcquisitionError(
            "Karaoke download needs "
            f"{required:,} free bytes including the safety reserve; "
            f"{available:,} are available"
        )


class KaraokeAcquisitionManager:
    def __init__(
        self,
        descriptor: ModuleDescriptor,
        *,
        on_complete: Callable[[], Any] | None = None,
    ) -> None:
        self.descriptor = descriptor
        self.on_complete = on_complete
        self._lock = threading.Lock()
        self._runner: threading.Thread | None = None
        self._active_job_id: str | None = None
        self._pending: deque[
            tuple[str, dict[str, Any], threading.Event]
        ] = deque()
        self._cancel: dict[str, threading.Event] = {}
        with catalog.open_catalog(descriptor.database) as connection:
            catalog.recover_interrupted_jobs(connection)

    def search(self, query: str, limit: int = 20) -> list[dict[str, Any]]:
        return kara_moe.search(
            query,
            user_agent=self.descriptor.user_agent,
            size=limit,
        )

    def detail(self, provider_id: str) -> dict[str, Any]:
        raw = kara_moe.detail(
            provider_id,
            user_agent=self.descriptor.user_agent,
        )
        return {
            **kara_moe.normalize(raw),
            "source": kara_moe.sanitized_metadata(raw),
            "cues": lyrics.normalize_cues(raw.get("lyrics")),
        }

    def plan(
        self,
        provider_id: str,
        *,
        max_bytes: int = DEFAULT_MAX_BYTES,
    ) -> dict[str, Any]:
        if max_bytes <= 0 or max_bytes > 20 * 1024 * 1024 * 1024:
            raise ValueError("Karaoke byte limit is outside the supported range")
        raw = kara_moe.detail(
            provider_id,
            user_agent=self.descriptor.user_agent,
        )
        normalized = kara_moe.normalize(raw)
        base_destination = storage.item_directory_name(
            normalized["provider_id"], normalized["title"]
        )
        token = uuid4().hex
        library_root = self.descriptor.home / "media" / "library"
        existing_destination = library_root / base_destination
        replacement = existing_destination.exists()
        destination = (
            f"{base_destination} - replacement-{token[:8]}"
            if replacement
            else base_destination
        )
        selection = {
            "provider": "kara-moe",
            "provider_id": normalized["provider_id"],
            "asset": "official-hardsub",
            "destination": destination,
            "max_bytes": max_bytes,
            "replacement": replacement,
        }
        selection_sha256 = _selection_sha(selection)
        expires_at = (
            datetime.now(timezone.utc) + timedelta(minutes=PLAN_LIFETIME_MINUTES)
        ).isoformat()
        payload = {
            "token": token,
            "selection_sha256": selection_sha256,
            "selection": selection,
            "item": normalized,
            "source": kara_moe.sanitized_metadata(raw),
            "estimated_bytes": kara_moe.estimated_media_bytes(raw),
            "replacement": replacement,
            "replacement_of": (
                normalized["item_id"] if replacement else None
            ),
            "expires_at": expires_at,
            "authorization_required": True,
            "files": [
                "video.mp4",
                "thumbnail.jpg",
                "source.metadata.json",
                "acquisition.receipt.json",
                "lyrics.normalized.json",
                "lyrics.generated.vtt",
                "lyrics.generated.lrc",
            ],
        }
        with catalog.open_catalog(self.descriptor.database) as connection:
            catalog.store_plan(
                connection,
                token=token,
                provider_id=normalized["provider_id"],
                selection_sha256=selection_sha256,
                payload=payload,
                expires_at=expires_at,
            )
        return payload

    def _plan_for_start(
        self,
        token: str,
        selection_sha256: str,
    ) -> dict[str, Any]:
        with catalog.open_catalog(self.descriptor.database) as connection:
            record = catalog.get_plan(connection, token)
            if record is None:
                raise KaraokeAcquisitionError(
                    "Karaoke acquisition plan is unavailable or already used"
                )
            expires = datetime.fromisoformat(record["expires_at"])
            if expires <= datetime.now(timezone.utc):
                raise KaraokeAcquisitionError("Karaoke acquisition plan expired")
            if record["selection_sha256"] != selection_sha256:
                raise KaraokeAcquisitionError(
                    "Karaoke acquisition selection changed; make a new plan"
                )
            if not catalog.consume_plan(connection, token):
                raise KaraokeAcquisitionError(
                    "Karaoke acquisition plan was already confirmed"
                )
            return record["payload"]

    def _ensure_runner_locked(self) -> None:
        if self._runner is not None and self._runner.is_alive():
            return
        self._runner = threading.Thread(
            target=self._run_queue,
            daemon=True,
            name="karaoke-acquisition-queue",
        )
        self._runner.start()

    def _enqueue_locked(
        self,
        job_id: str,
        plan: dict[str, Any],
        cancel_event: threading.Event,
    ) -> None:
        self._cancel[job_id] = cancel_event
        self._pending.append((job_id, plan, cancel_event))
        self._ensure_runner_locked()

    def _run_queue(self) -> None:
        while True:
            with self._lock:
                if not self._pending:
                    self._active_job_id = None
                    self._runner = None
                    return
                job_id, plan, cancel_event = self._pending.popleft()
                self._active_job_id = job_id
            if cancel_event.is_set():
                self._update(
                    job_id,
                    status="cancelled",
                    phase="cancelled",
                    error="Karaoke download was cancelled before it started",
                )
            else:
                self._worker(job_id, plan, cancel_event)
            with self._lock:
                self._cancel.pop(job_id, None)
                if self._active_job_id == job_id:
                    self._active_job_id = None

    def start(
        self,
        *,
        token: str,
        selection_sha256: str,
        authorized: bool,
    ) -> dict[str, Any]:
        if not authorized:
            raise KaraokeAcquisitionError(
                "Confirm that you are authorized to download this karaoke"
            )
        with self._lock:
            plan = self._plan_for_start(token, selection_sha256)
            job_id = uuid4().hex
            with catalog.open_catalog(self.descriptor.database) as connection:
                job = catalog.create_job(
                    connection,
                    job_id=job_id,
                    plan_token=token,
                    provider_id=plan["selection"]["provider_id"],
                )
            cancel_event = threading.Event()
            self._enqueue_locked(job_id, plan, cancel_event)
            return job

    def resume(self, job_id: str) -> dict[str, Any]:
        with self._lock:
            with catalog.open_catalog(self.descriptor.database) as connection:
                job = catalog.get_job(connection, job_id)
                if job is None:
                    raise KaraokeAcquisitionError("Unknown Karaoke job")
                if job["status"] not in {"cancelled", "failed", "interrupted"}:
                    raise KaraokeAcquisitionError("Karaoke job is not resumable")
                plan_record = catalog.get_plan(
                    connection, job["plan_token"], allow_consumed=True
                )
                if plan_record is None:
                    raise KaraokeAcquisitionError("Karaoke job plan is unavailable")
                job = catalog.update_job(
                    connection,
                    job_id,
                    status="queued",
                    phase="queued",
                    error="",
                )
            cancel_event = threading.Event()
            self._enqueue_locked(job_id, plan_record["payload"], cancel_event)
            return job

    def cancel(self, job_id: str) -> dict[str, Any]:
        event = self._cancel.get(job_id)
        if event is None:
            raise KaraokeAcquisitionError("Karaoke job is not running")
        event.set()
        with self._lock:
            queued = any(entry[0] == job_id for entry in self._pending)
            if queued:
                self._pending = deque(
                    entry for entry in self._pending if entry[0] != job_id
                )
                self._cancel.pop(job_id, None)
        if queued:
            return self._update(
                job_id,
                status="cancelled",
                phase="cancelled",
                error="Karaoke download was cancelled before it started",
            )
        return self.job(job_id)

    def job(self, job_id: str) -> dict[str, Any]:
        with catalog.open_catalog(self.descriptor.database) as connection:
            value = catalog.get_job(connection, job_id)
        if value is None:
            raise KaraokeAcquisitionError("Unknown Karaoke job")
        return value

    def jobs(self) -> list[dict[str, Any]]:
        with catalog.open_catalog(self.descriptor.database) as connection:
            return catalog.list_jobs(connection)

    def _update(self, job_id: str, **values: Any) -> dict[str, Any]:
        with catalog.open_catalog(self.descriptor.database) as connection:
            return catalog.update_job(connection, job_id, **values)

    def _worker(
        self,
        job_id: str,
        plan: dict[str, Any],
        cancel_event: threading.Event,
    ) -> None:
        layout = storage.ensure_layout(self.descriptor.home)
        stage = layout["staging"] / job_id
        stage.mkdir(parents=True, exist_ok=True)
        selection = plan["selection"]
        normalized = plan["item"]
        video = stage / "video.mp4"
        partial = video.with_name(video.name + ".part")
        remaining = max(
            int(plan.get("estimated_bytes") or 0)
            - (partial.stat().st_size if partial.is_file() else 0),
            0,
        )
        last_progress = 0.0

        def progress(downloaded: int, total: int | None) -> None:
            nonlocal last_progress
            now = time.monotonic()
            if now - last_progress < 0.25 and downloaded != total:
                return
            last_progress = now
            ratio = min(downloaded / total, 1.0) if total else 0.0
            self._update(
                job_id,
                status="running",
                phase="downloading",
                progress=round(ratio * 0.85, 4),
                downloaded_bytes=downloaded,
                total_bytes=total,
            )

        try:
            _require_free_space(layout["staging"], remaining)
            self._update(job_id, status="running", phase="downloading")
            if video.is_file():
                media_result = {
                    "final_url": f"{kara_moe.API_BASE}/karas/"
                    f"{selection['provider_id']}/hardsub",
                    "content_type": "video/mp4",
                    "bytes": video.stat().st_size,
                    "resumed_completed_stage": True,
                }
            else:
                media_result = kara_moe.download_hardsub(
                    selection["provider_id"],
                    video,
                    user_agent=self.descriptor.user_agent,
                    max_bytes=int(selection["max_bytes"]),
                    timeout=30,
                    on_progress=progress,
                    cancel_event=cancel_event,
                )
            if cancel_event.is_set():
                raise KaraokeAcquisitionError("Karaoke download was cancelled")
            primary_sha, primary_size = storage.hash_file(video)
            integrity = storage.mp4_integrity(video)
            if not integrity["complete"]:
                if partial.exists():
                    raise KaraokeAcquisitionError(
                        "Both completed and resumable Karaoke staging files exist; "
                        "manual inspection is required."
                    )
                video.replace(partial)
                expected = integrity.get("expected_bytes")
                byte_detail = (
                    f"received {primary_size:,} of {int(expected):,} declared bytes"
                    if expected
                    else f"received {primary_size:,} bytes"
                )
                raise KaraokeAcquisitionError(
                    "Kara.moe returned an incomplete media file: "
                    f"{byte_detail} ({integrity['reason']}). "
                    "The partial remains in staging and can be resumed."
                )
            self._update(job_id, phase="indexing", progress=0.88)
            source = plan["source"]
            cues = lyrics.normalize_cues(source.get("lyrics"))
            storage.write_json_create(stage / "source.metadata.json", source)
            storage.write_json_create(stage / "lyrics.normalized.json", cues)
            lyric_records: list[dict[str, Any]] = []
            language = _language(source, normalized)
            if cues:
                vtt = stage / "lyrics.generated.vtt"
                lrc = stage / "lyrics.generated.lrc"
                storage.write_text_create(vtt, lyrics.to_webvtt(cues))
                storage.write_text_create(lrc, lyrics.to_lrc(cues))
                for path, format_name in ((vtt, "vtt"), (lrc, "lrc")):
                    digest, _ = storage.hash_file(path)
                    lyric_records.append(
                        {
                            "lyric_id": f"kara-moe:{selection['provider_id']}:"
                            f"generated-{format_name}",
                            "label": (
                                f"{language} generated timing"
                                if language
                                else "Generated timing"
                            ),
                            "language": language,
                            "format": format_name,
                            "source_kind": "upstream-normalized-generated",
                            "relative_path": "",
                            "sha256": digest,
                            "cues": cues,
                        }
                    )
            thumbnail = stage / "thumbnail.jpg"
            thumbnail_created = storage.create_video_thumbnail(video, thumbnail)
            receipt = {
                "format": "keivotos-karaoke-acquisition-receipt-v1",
                "provider": "kara-moe",
                "provider_id": selection["provider_id"],
                "selection_sha256": plan["selection_sha256"],
                "acquired_at": _now(),
                "media": {
                    **media_result,
                    "sha256": primary_sha,
                    "bytes": primary_size,
                },
                "lyrics": {
                    "normalized_cues": len(cues),
                    "generated": ["vtt", "lrc"] if cues else [],
                    "original_ass_claimed": False,
                },
                "thumbnail_created": thumbnail_created,
                "replacement": bool(plan.get("replacement")),
                "replacement_of": plan.get("replacement_of"),
            }
            storage.write_json_create(stage / "acquisition.receipt.json", receipt)
            destination = layout["library"] / selection["destination"]
            storage.publish_staged_directory(stage, destination)
            directory = destination.relative_to(layout["library"]).as_posix()
            for record in lyric_records:
                record["relative_path"] = (
                    f"{directory}/lyrics.generated.{record['format']}"
                )
            obsolete_primary = None
            if plan.get("replacement_of"):
                with catalog.open_catalog(
                    self.descriptor.database
                ) as connection:
                    previous = catalog.get_item(
                        connection, str(plan["replacement_of"])
                    )
                if previous is not None:
                    obsolete_primary = previous.get("primary_video")
            item = {
                "item_id": normalized["item_id"],
                "provider": "kara-moe",
                "provider_id": selection["provider_id"],
                "title": normalized["title"],
                "subtitle": normalized.get("subtitle", ""),
                "year": normalized.get("year"),
                "duration": normalized.get("duration"),
                "primary_video": f"{directory}/video.mp4",
                "thumbnail": (
                    f"{directory}/thumbnail.jpg" if thumbnail_created else None
                ),
                "metadata_path": f"{directory}/source.metadata.json",
                "receipt_path": f"{directory}/acquisition.receipt.json",
                "primary_sha256": primary_sha,
                "metadata": {
                    **source,
                    "_keivotos": {
                        "replacement": bool(plan.get("replacement")),
                        "obsolete_primary_video": obsolete_primary,
                    },
                },
            }
            with catalog.open_catalog(self.descriptor.database) as connection:
                catalog.upsert_item(
                    connection,
                    item,
                    normalized.get("tags", {}),
                    lyric_records,
                )
            if self.on_complete is not None:
                self.on_complete()
            self._update(
                job_id,
                status="completed",
                phase="completed",
                progress=1.0,
                downloaded_bytes=primary_size,
                total_bytes=primary_size,
                item_id=normalized["item_id"],
            )
        except Exception as exc:
            cancelled = cancel_event.is_set() or "cancel" in str(exc).casefold()
            self._update(
                job_id,
                status="cancelled" if cancelled else "failed",
                phase="cancelled" if cancelled else "failed",
                error=str(exc)[:2000],
            )
