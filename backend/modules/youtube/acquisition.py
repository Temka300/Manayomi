"""Plan-confirm YouTube acquisition using the shared guarded yt-dlp service."""
from __future__ import annotations

from collections import deque
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import shutil
import threading
from typing import Any, Callable
from uuid import uuid4

from module_descriptor import ModuleDescriptor
from modules.youtube import catalog, provider, storage
from services import yt_dlp as yt_dlp_service
from thumbnails import resolve_ffmpeg_executable


DEFAULT_MAX_BYTES = 4 * 1024 * 1024 * 1024
PLAN_LIFETIME_MINUTES = 60
AUDIO_FORMATS = {"none", "best", "m4a", "opus", "mp3"}
AUDIO_QUALITIES = {"128K", "192K", "320K"}
COOKIE_BROWSERS = {"none", "chrome", "edge", "firefox"}
PROGRESS_PREFIX = "keivotos-progress:"
MIN_FREE_BYTES = 512 * 1024 * 1024
POSTPROCESS_MARGIN_BYTES = 64 * 1024 * 1024


class YouTubeAcquisitionError(RuntimeError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _selection_sha(value: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()


def _number(value: str) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def _require_free_space(path: Path, plan: dict[str, Any]) -> None:
    estimated = int(plan.get("estimated_bytes") or 0)
    if plan["selection"]["audio_format"] != "none":
        estimated *= 2
    required = MIN_FREE_BYTES + POSTPROCESS_MARGIN_BYTES + estimated
    available = shutil.disk_usage(path).free
    if available < required:
        raise YouTubeAcquisitionError(
            "YouTube download needs "
            f"{required:,} free bytes including post-processing and safety "
            f"reserves; {available:,} are available"
        )


class YouTubeAcquisitionManager:
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
        layout = storage.ensure_layout(self.descriptor.home)
        results = provider.search(query, limit=limit)
        for item in results:
            thumbnail_url = item.pop("thumbnail_url", None)
            item["thumbnail_cache_id"] = None
            if thumbnail_url:
                try:
                    item["thumbnail_cache_id"] = provider.cache_thumbnail(
                        thumbnail_url,
                        layout["thumbnail_cache"],
                        user_agent=self.descriptor.user_agent,
                    )
                except provider.YouTubeProviderError:
                    pass
        return results

    def inspect(self, video_id: str) -> dict[str, Any]:
        return provider.inspect(video_id)

    def plan(
        self,
        *,
        video_id: str,
        resolution: str,
        compatibility: bool,
        audio_format: str,
        audio_quality: str,
        subtitle_languages: list[str],
        automatic_captions: bool,
        karaoke_intent: bool,
        browser_session: str = "none",
        max_bytes: int = DEFAULT_MAX_BYTES,
    ) -> dict[str, Any]:
        if max_bytes <= 0 or max_bytes > 20 * 1024 * 1024 * 1024:
            raise ValueError("YouTube byte limit is outside the supported range")
        if audio_format not in AUDIO_FORMATS:
            raise ValueError("Unsupported companion audio format")
        if audio_quality not in AUDIO_QUALITIES:
            raise ValueError("Unsupported companion audio quality")
        if browser_session not in COOKIE_BROWSERS:
            raise ValueError("Unsupported browser session source")
        metadata = provider.inspect(video_id)
        selected = provider.select_formats(
            metadata,
            resolution=resolution,
            compatibility=compatibility,
        )
        available_manual = set(metadata.get("subtitles", {}))
        available_auto = set(metadata.get("automatic_captions", {}))
        languages = []
        subtitle_sources: dict[str, str] = {}
        for language in subtitle_languages[:10]:
            clean = str(language).strip()
            if clean and (
                clean in available_manual
                or (automatic_captions and clean in available_auto)
            ) and clean not in languages:
                languages.append(clean)
                subtitle_sources[clean] = (
                    "manual" if clean in available_manual else "automatic"
                )
        selection = {
            "provider": "youtube",
            "video_id": metadata["video_id"],
            "resolution": resolution,
            "quality_label": selected["quality_label"],
            "compatibility": compatibility,
            "format_selector": selected["selector"],
            "format_ids": [
                value["format_id"] for value in selected["selected"]
            ],
            "audio_format": audio_format,
            "audio_quality": audio_quality,
            "subtitle_languages": languages,
            "subtitle_sources": subtitle_sources,
            "automatic_captions": automatic_captions,
            "karaoke_intent": karaoke_intent,
            "browser_session": browser_session,
            "max_bytes": max_bytes,
        }
        selection_sha256 = _selection_sha(selection)
        token = uuid4().hex
        expires_at = (
            datetime.now(timezone.utc) + timedelta(minutes=PLAN_LIFETIME_MINUTES)
        ).isoformat()
        display_quality = (
            f"{selected['quality_label']} compatible"
            if compatibility
            else f"{selected['quality_label']} source"
        )
        destination = storage.item_directory_name(
            metadata["video_id"],
            f"{metadata['title']} [{display_quality}]",
        )
        library = storage.ensure_layout(self.descriptor.home)["library"]
        replacement = (library / destination).exists()
        if replacement:
            destination = f"{destination} - replacement-{token[:8]}"
        payload = {
            "token": token,
            "selection_sha256": selection_sha256,
            "selection": selection,
            "metadata": {
                key: value
                for key, value in metadata.items()
                if key not in {"formats", "sanitized_metadata"}
            },
            "source_metadata": metadata["sanitized_metadata"],
            "selected_formats": selected["selected"],
            "estimated_bytes": selected["estimated_bytes"],
            "display_quality": display_quality,
            "destination": destination,
            "replacement": replacement,
            "expires_at": expires_at,
            "authorization_required": True,
            "files": {
                "video": True,
                "companion_audio": audio_format != "none",
                "thumbnail": True,
                "subtitle_languages": languages,
                "metadata_receipt": True,
            },
        }
        with catalog.open_catalog(self.descriptor.database) as connection:
            catalog.store_plan(
                connection,
                token=token,
                video_id=metadata["video_id"],
                selection_sha256=selection_sha256,
                payload=payload,
                expires_at=expires_at,
            )
        return payload

    def _plan_for_start(
        self, token: str, selection_sha256: str
    ) -> dict[str, Any]:
        with catalog.open_catalog(self.descriptor.database) as connection:
            record = catalog.get_plan(connection, token)
            if record is None:
                raise YouTubeAcquisitionError(
                    "YouTube acquisition plan is unavailable or already used"
                )
            if datetime.fromisoformat(record["expires_at"]) <= datetime.now(
                timezone.utc
            ):
                raise YouTubeAcquisitionError("YouTube acquisition plan expired")
            if record["selection_sha256"] != selection_sha256:
                raise YouTubeAcquisitionError(
                    "YouTube format selection changed; make a new plan"
                )
            if not catalog.consume_plan(connection, token):
                raise YouTubeAcquisitionError(
                    "YouTube acquisition plan was already confirmed"
                )
            return record["payload"]

    def _ensure_runner_locked(self) -> None:
        if self._runner is not None and self._runner.is_alive():
            return
        self._runner = threading.Thread(
            target=self._run_queue,
            daemon=True,
            name="youtube-acquisition-queue",
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
                    error="YouTube download was cancelled before it started",
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
            raise YouTubeAcquisitionError(
                "Confirm that this YouTube download is authorized"
            )
        with self._lock:
            plan = self._plan_for_start(token, selection_sha256)
            job_id = uuid4().hex
            with catalog.open_catalog(self.descriptor.database) as connection:
                job = catalog.create_job(
                    connection,
                    job_id=job_id,
                    plan_token=token,
                    video_id=plan["selection"]["video_id"],
                )
            event = threading.Event()
            self._enqueue_locked(job_id, plan, event)
            return job

    def resume(self, job_id: str) -> dict[str, Any]:
        with self._lock:
            with catalog.open_catalog(self.descriptor.database) as connection:
                job = catalog.get_job(connection, job_id)
                if job is None:
                    raise YouTubeAcquisitionError("Unknown YouTube job")
                if job["status"] not in {"cancelled", "failed", "interrupted"}:
                    raise YouTubeAcquisitionError("YouTube job is not resumable")
                plan = catalog.get_plan(
                    connection, job["plan_token"], allow_consumed=True
                )
                if plan is None:
                    raise YouTubeAcquisitionError("YouTube job plan is unavailable")
                job = catalog.update_job(
                    connection,
                    job_id,
                    status="queued",
                    phase="queued",
                    error="",
                )
            event = threading.Event()
            self._enqueue_locked(job_id, plan["payload"], event)
            return job

    def cancel(self, job_id: str) -> dict[str, Any]:
        event = self._cancel.get(job_id)
        if event is None:
            raise YouTubeAcquisitionError("YouTube job is not running")
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
                error="YouTube download was cancelled before it started",
            )
        return self.job(job_id)

    def job(self, job_id: str) -> dict[str, Any]:
        with catalog.open_catalog(self.descriptor.database) as connection:
            value = catalog.get_job(connection, job_id)
        if value is None:
            raise YouTubeAcquisitionError("Unknown YouTube job")
        return value

    def jobs(self) -> list[dict[str, Any]]:
        with catalog.open_catalog(self.descriptor.database) as connection:
            return catalog.list_jobs(connection)

    def _update(self, job_id: str, **values: Any) -> dict[str, Any]:
        with catalog.open_catalog(self.descriptor.database) as connection:
            return catalog.update_job(connection, job_id, **values)

    def _media_command(self, plan: dict[str, Any], stage: Path) -> list[str]:
        selection = plan["selection"]
        command = [
            *yt_dlp_service.resolve_command(error_type=YouTubeAcquisitionError),
            *yt_dlp_service.common_download_args(
                retries=3,
                socket_timeout=30,
                ffmpeg_executable=resolve_ffmpeg_executable(),
            ),
            "--newline",
            "--no-colors",
            "--progress-template",
            (
                "download:"
                f"{PROGRESS_PREFIX}"
                "%(progress.status)s|%(progress.downloaded_bytes)s|"
                "%(progress.total_bytes,progress.total_bytes_estimate)s|"
                "%(progress.speed)s|%(progress.eta)s"
            ),
            "--max-filesize",
            str(selection["max_bytes"]),
            "--format",
            selection["format_selector"],
            "--output",
            str(stage / "media.%(ext)s"),
            "--write-thumbnail",
            "--convert-thumbnails",
            "jpg",
        ]
        if selection["compatibility"]:
            command.extend(["--merge-output-format", "mp4"])
        if selection.get("browser_session", "none") != "none":
            command.extend(
                ["--cookies-from-browser", selection["browser_session"]]
            )
        if selection["audio_format"] != "none":
            command.extend(["--extract-audio", "--keep-video"])
            if selection["audio_format"] != "best":
                command.extend(
                    ["--audio-format", selection["audio_format"]]
                )
            command.extend(["--audio-quality", selection["audio_quality"]])
        command.append(provider.watch_url(selection["video_id"]))
        return command

    # Compatibility seam retained for tests and callers that inspected the
    # original single-stage command. It now deliberately means media only.
    def _command(self, plan: dict[str, Any], stage: Path) -> list[str]:
        return self._media_command(plan, stage)

    def _subtitle_command(
        self, plan: dict[str, Any], stage: Path
    ) -> list[str] | None:
        selection = plan["selection"]
        languages = selection["subtitle_languages"]
        if not languages:
            return None
        command = [
            *yt_dlp_service.resolve_command(error_type=YouTubeAcquisitionError),
            *yt_dlp_service.common_download_args(
                retries=6,
                socket_timeout=45,
                ffmpeg_executable=resolve_ffmpeg_executable(),
            ),
            "--skip-download",
            "--write-subs",
            "--sub-langs",
            ",".join(languages),
            "--sub-format",
            "ass/srt/vtt/best",
            "--convert-subs",
            "vtt",
            "--sleep-subtitles",
            "2",
            "--retry-sleep",
            "http:exp=2:10",
            "--retry-sleep",
            "fragment:exp=2:10",
            "--output",
            str(stage / "media.%(ext)s"),
        ]
        if "automatic" in selection.get("subtitle_sources", {}).values():
            command.append("--write-auto-subs")
        if selection.get("browser_session", "none") != "none":
            command.extend(
                ["--cookies-from-browser", selection["browser_session"]]
            )
        command.append(provider.watch_url(selection["video_id"]))
        return command

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

        def on_line(line: str) -> None:
            if not line.startswith(PROGRESS_PREFIX):
                return
            fields = line.removeprefix(PROGRESS_PREFIX).split("|")
            fields += [""] * (5 - len(fields))
            status, downloaded, total, speed, eta = fields[:5]
            downloaded_value = int(_number(downloaded) or 0)
            total_value = int(_number(total) or 0) or None
            ratio = (
                min(downloaded_value / total_value, 1.0)
                if total_value
                else 0.0
            )
            self._update(
                job_id,
                status="running",
                phase=(
                    "downloading"
                    if status not in {"finished", "postprocessing"}
                    else "post-processing"
                ),
                progress=round(ratio * 0.85, 4),
                downloaded_bytes=downloaded_value,
                total_bytes=total_value,
                speed=_number(speed),
                eta=_number(eta),
            )

        try:
            _require_free_space(layout["staging"], plan)
            self._update(job_id, status="running", phase="downloading")
            yt_dlp_service.run_streaming_process(
                self._media_command(plan, stage),
                timeout=4 * 60 * 60,
                on_line=on_line,
                cancel_event=cancel_event,
                label="yt-dlp YouTube acquisition",
                error_type=YouTubeAcquisitionError,
            )
            if cancel_event.is_set():
                raise YouTubeAcquisitionError("YouTube download was cancelled")
            subtitle_warning = ""
            subtitle_command = self._subtitle_command(plan, stage)
            if subtitle_command is not None:
                self._update(job_id, phase="subtitles", progress=0.87)
                try:
                    yt_dlp_service.run_streaming_process(
                        subtitle_command,
                        timeout=30 * 60,
                        on_line=lambda _line: None,
                        cancel_event=cancel_event,
                        label="yt-dlp YouTube subtitles",
                        error_type=YouTubeAcquisitionError,
                    )
                except YouTubeAcquisitionError as exc:
                    if cancel_event.is_set():
                        raise
                    # Captions are optional. YouTube may rate-limit a caption
                    # endpoint even after the media streams have completed;
                    # preserve and publish the playable video, and surface a
                    # resumable warning instead of discarding that work.
                    subtitle_warning = (
                        "Video downloaded, but one or more requested subtitles "
                        f"could not be fetched: {str(exc)[:900]}"
                    )
            self._update(job_id, phase="indexing", progress=0.9)
            files = [
                path
                for path in stage.iterdir()
                if path.is_file()
                and not path.name.endswith((".part", ".ytdl", ".writing"))
            ]
            videos = [path for path in files if path.suffix.casefold() in storage.VIDEO_SUFFIXES]
            if not videos:
                raise YouTubeAcquisitionError(
                    "yt-dlp completed without a playable local video"
                )
            video = max(videos, key=lambda path: path.stat().st_size)
            audio = [
                path for path in files if path.suffix.casefold() in storage.AUDIO_SUFFIXES
            ]
            subtitles = [
                path for path in files if path.suffix.casefold() in storage.SUBTITLE_SUFFIXES
            ]
            thumbnails = [
                path for path in files if path.suffix.casefold() in storage.IMAGE_SUFFIXES
            ]
            video_sha, video_size = storage.hash_file(video)
            metadata = plan["metadata"]
            receipt = {
                "format": "keivotos-youtube-acquisition-receipt-v1",
                "source": provider.watch_url(selection["video_id"]),
                "selection_sha256": plan["selection_sha256"],
                "acquired_at": _now(),
                "selected_formats": plan["selected_formats"],
                "quality": plan["display_quality"],
                "video": {
                    "filename": video.name,
                    "sha256": video_sha,
                    "bytes": video_size,
                },
                "audio": [path.name for path in audio],
                "subtitles": [path.name for path in subtitles],
                "subtitle_warning": subtitle_warning,
                "authorization_confirmed": True,
                "replacement": bool(plan.get("replacement")),
            }
            storage.write_json_create(
                stage / "source.metadata.json", plan["source_metadata"]
            )
            storage.write_json_create(
                stage / "acquisition.receipt.json", receipt
            )
            destination = layout["library"] / plan["destination"]
            storage.publish_staged_directory(stage, destination)
            directory = destination.relative_to(layout["library"]).as_posix()
            item_id = (
                f"youtube:{selection['video_id']}:"
                f"{hashlib.sha256(plan['selection_sha256'].encode()).hexdigest()[:12]}"
            )
            item = {
                "item_id": item_id,
                "video_id": selection["video_id"],
                "title": metadata["title"],
                "channel": metadata.get("channel", ""),
                "duration": metadata.get("duration"),
                "upload_date": metadata.get("upload_date"),
                "view_count": metadata.get("view_count"),
                "quality_label": plan["display_quality"],
                "video_path": f"{directory}/{video.name}",
                "video_sha256": video_sha,
                "thumbnail_path": (
                    f"{directory}/{thumbnails[0].name}" if thumbnails else None
                ),
                "audio_paths": [f"{directory}/{path.name}" for path in audio],
                "subtitles": [
                    {
                        "path": f"{directory}/{path.name}",
                        "format": path.suffix.casefold().lstrip("."),
                        "automatic": any(
                            source == "automatic"
                            and (
                                path.stem.endswith(f".{language}")
                                or f".{language}." in f".{path.name}."
                            )
                            for language, source in selection.get(
                                "subtitle_sources", {}
                            ).items()
                        ),
                    }
                    for path in subtitles
                ],
                "metadata_path": f"{directory}/source.metadata.json",
                "receipt_path": f"{directory}/acquisition.receipt.json",
                "metadata": plan["source_metadata"],
                "karaoke_intent": selection["karaoke_intent"],
            }
            with catalog.open_catalog(self.descriptor.database) as connection:
                previous = catalog.get_item(connection, item_id)
                if previous is not None:
                    item["metadata"] = dict(item["metadata"])
                    suite_metadata = dict(item["metadata"].get("_keivotos") or {})
                    suite_metadata["obsolete_primary_video"] = previous["video_path"]
                    item["metadata"]["_keivotos"] = suite_metadata
                    catalog.update_item(connection, item)
                else:
                    catalog.insert_item(connection, item)
            publish_error = subtitle_warning
            if self.on_complete is not None:
                try:
                    self.on_complete()
                except Exception as exc:
                    publish_error = (
                        (publish_error + " ") if publish_error else ""
                    ) + (
                        "Download completed; Files publication will retry at "
                        f"startup: {str(exc)[:500]}"
                    )
            self._update(
                job_id,
                status="completed",
                phase="completed",
                progress=1.0,
                downloaded_bytes=video_size,
                total_bytes=video_size,
                item_id=item_id,
                error=publish_error,
            )
        except Exception as exc:
            cancelled = cancel_event.is_set() or "cancel" in str(exc).casefold()
            self._update(
                job_id,
                status="cancelled" if cancelled else "failed",
                phase="cancelled" if cancelled else "failed",
                error=str(exc)[:2000],
            )
        finally:
            # Queue ownership removes the cancellation token after the worker
            # returns so queued and active jobs share one lifecycle.
            pass
