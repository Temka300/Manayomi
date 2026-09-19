"""HTTP surface for local, explicit YouTube acquisition and playback."""
from __future__ import annotations

import mimetypes
from pathlib import Path
import re
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse, Response, StreamingResponse
from pydantic import BaseModel, Field

import config
from database import get_user_db
from files_base import index as files_index
from files_base import serving, sources as files_sources
from modules.youtube import catalog, provider, storage
from modules.youtube.acquisition import (
    DEFAULT_MAX_BYTES,
    MIN_FREE_BYTES,
    POSTPROCESS_MARGIN_BYTES,
    YouTubeAcquisitionError,
    YouTubeAcquisitionManager,
)
from modules.youtube.provider import YouTubeProviderError
import suite_modules


router = APIRouter(prefix="/api/youtube", tags=["youtube"])
DESCRIPTOR = config.MODULE_REGISTRY.require("youtube")
LIBRARY_ROOT = DESCRIPTOR.home / "media" / "library"
THUMBNAIL_ID_RE = re.compile(r"^[0-9a-f]{64}\.(?:avif|jpg|png|webp)$")


class YouTubePlanPayload(BaseModel):
    video_id: str = Field(min_length=11, max_length=11)
    resolution: Literal["480", "720", "1080", "1440", "2160", "highest"] = "1080"
    compatibility: bool = True
    audio_format: Literal["none", "best", "m4a", "opus", "mp3"] = "none"
    audio_quality: Literal["128K", "192K", "320K"] = "192K"
    subtitle_languages: list[str] = Field(default_factory=list, max_length=10)
    automatic_captions: bool = False
    karaoke_intent: bool = False
    browser_session: Literal["none", "chrome", "edge", "firefox"] = "none"
    max_bytes: int = Field(default=DEFAULT_MAX_BYTES, gt=0, le=20 * 1024 * 1024 * 1024)


class YouTubeDownloadPayload(BaseModel):
    plan_token: str = Field(min_length=32, max_length=64)
    selection_sha256: str = Field(min_length=64, max_length=64)
    authorized: bool


class YouTubePlaybackPayload(BaseModel):
    position_seconds: float = Field(default=0, ge=0)
    duration_seconds: float | None = Field(default=None, ge=0)
    completed: bool = False


def _require_enabled() -> None:
    with get_user_db() as connection:
        suite_modules.ensure_schema(connection)
        enabled = suite_modules.enabled_ids(connection)
    if DESCRIPTOR.slug not in enabled:
        raise HTTPException(status_code=409, detail="YouTube module is disabled")


def _publish_library() -> dict[str, Any]:
    if not LIBRARY_ROOT.is_dir():
        return {"published": False, "source_id": None, "scan": None}
    with get_user_db() as user_connection:
        DESCRIPTOR.publish(user_connection)
        source_id = files_sources.deterministic_source_id(LIBRARY_ROOT)
        source = files_sources.get_source(user_connection, source_id)
        all_sources = files_sources.list_sources(user_connection)
    if source is None:
        return {"published": False, "source_id": None, "scan": None}
    excluded = [
        Path(candidate.path)
        for candidate in files_sources.descendant_sources(source, all_sources)
    ]
    with files_index.open_index(config.FILES_DB_PATH) as index_connection:
        scan = files_index.scan_source(
            index_connection,
            source.source_id,
            Path(source.path),
            excluded_roots=excluded,
        )
    return {"published": True, "source_id": source.source_id, "scan": scan}


_MANAGER: YouTubeAcquisitionManager | None = None


def _manager() -> YouTubeAcquisitionManager:
    global _MANAGER
    if _MANAGER is None:
        _MANAGER = YouTubeAcquisitionManager(
            DESCRIPTOR,
            on_complete=_publish_library,
        )
    return _MANAGER


def _enrich(item: dict[str, Any]) -> dict[str, Any]:
    item["files_source_id"] = files_sources.deterministic_source_id(LIBRARY_ROOT)
    item["files_relative_path"] = item["video_path"]
    with catalog.open_catalog(DESCRIPTOR.database) as connection:
        item["playback"] = catalog.playback_state(connection, item["item_id"])
    return item


def _item_or_404(item_id: str) -> dict[str, Any]:
    with catalog.open_catalog(DESCRIPTOR.database) as connection:
        item = catalog.get_item(connection, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Unknown YouTube library item")
    return _enrich(item)


@router.get("/status")
def status() -> dict[str, Any]:
    _require_enabled()
    layout = storage.ensure_layout(DESCRIPTOR.home)
    with catalog.open_catalog(DESCRIPTOR.database) as connection:
        count = connection.execute(
            "SELECT COUNT(*) AS count FROM youtube_items"
        ).fetchone()["count"]
    return {
        "format": "keivotos-youtube-status-v1",
        "initialized": True,
        "items": count,
        "jobs": _manager().jobs(),
        "storage": {key: str(value) for key, value in layout.items()},
        "limits": {
            "max_file_bytes": DEFAULT_MAX_BYTES,
            "minimum_free_bytes": MIN_FREE_BYTES,
            "postprocess_margin_bytes": POSTPROCESS_MARGIN_BYTES,
            "active_jobs": 1,
            "queued_jobs": True,
            "search_results": 30,
        },
        "policy": {
            "public_single_videos_only": True,
            "cookies": "optional-local-browser-session",
            "playlists": False,
            "arbitrary_sites": False,
        },
    }


@router.get("/search")
def search(
    query: str = Query(min_length=1, max_length=200),
    limit: int = Query(default=20, ge=1, le=30),
) -> dict[str, Any]:
    _require_enabled()
    try:
        items = _manager().search(query, limit)
    except (YouTubeProviderError, YouTubeAcquisitionError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "format": "keivotos-youtube-search-v1",
        "query": query,
        "items": items,
    }


@router.get("/videos/{video_id}")
def inspect_video(video_id: str) -> dict[str, Any]:
    _require_enabled()
    try:
        item = _manager().inspect(video_id)
    except (YouTubeProviderError, YouTubeAcquisitionError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"format": "keivotos-youtube-video-v1", "item": item}


@router.get("/inspect")
def inspect_url(
    url: str = Query(min_length=10, max_length=2000),
) -> dict[str, Any]:
    _require_enabled()
    try:
        video_id = provider.video_id_from_url(url)
        item = _manager().inspect(video_id)
    except (YouTubeProviderError, YouTubeAcquisitionError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"format": "keivotos-youtube-video-v1", "item": item}


@router.post("/plan")
def plan(payload: YouTubePlanPayload) -> dict[str, Any]:
    _require_enabled()
    try:
        value = _manager().plan(**payload.model_dump())
    except (YouTubeProviderError, YouTubeAcquisitionError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"format": "keivotos-youtube-plan-v1", "plan": value}


@router.post("/download", status_code=202)
def download(payload: YouTubeDownloadPayload) -> dict[str, Any]:
    _require_enabled()
    try:
        job = _manager().start(
            token=payload.plan_token,
            selection_sha256=payload.selection_sha256,
            authorized=payload.authorized,
        )
    except YouTubeAcquisitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"format": "keivotos-youtube-job-v1", "job": job}


@router.get("/jobs")
def jobs() -> dict[str, Any]:
    _require_enabled()
    return {"format": "keivotos-youtube-jobs-v1", "jobs": _manager().jobs()}


@router.get("/jobs/{job_id}")
def job(job_id: str) -> dict[str, Any]:
    _require_enabled()
    try:
        value = _manager().job(job_id)
    except YouTubeAcquisitionError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"format": "keivotos-youtube-job-v1", "job": value}


@router.post("/jobs/{job_id}/cancel")
def cancel_job(job_id: str) -> dict[str, Any]:
    _require_enabled()
    try:
        value = _manager().cancel(job_id)
    except YouTubeAcquisitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"format": "keivotos-youtube-job-v1", "job": value}


@router.post("/jobs/{job_id}/resume", status_code=202)
def resume_job(job_id: str) -> dict[str, Any]:
    _require_enabled()
    try:
        value = _manager().resume(job_id)
    except YouTubeAcquisitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"format": "keivotos-youtube-job-v1", "job": value}


@router.get("/library")
def library(
    query: str = Query(default="", max_length=200),
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    _require_enabled()
    with catalog.open_catalog(DESCRIPTOR.database) as connection:
        items = [
            _enrich(item)
            for item in catalog.list_items(
                connection,
                query=query,
                limit=limit,
                offset=offset,
            )
        ]
    return {"format": "keivotos-youtube-library-v1", "items": items}


@router.get("/library/{item_id}")
def library_item(item_id: str) -> dict[str, Any]:
    _require_enabled()
    return {
        "format": "keivotos-youtube-item-v1",
        "item": _item_or_404(item_id),
    }


@router.get("/library/{item_id}/playback")
def playback(item_id: str) -> dict[str, Any]:
    _require_enabled()
    _item_or_404(item_id)
    with catalog.open_catalog(DESCRIPTOR.database) as connection:
        value = catalog.playback_state(connection, item_id)
    return {"format": "keivotos-youtube-playback-v1", "playback": value}


@router.put("/library/{item_id}/playback")
def put_playback(
    item_id: str, payload: YouTubePlaybackPayload
) -> dict[str, Any]:
    _require_enabled()
    _item_or_404(item_id)
    with catalog.open_catalog(DESCRIPTOR.database) as connection:
        try:
            value = catalog.save_playback_state(
                connection, item_id, **payload.model_dump()
            )
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"format": "keivotos-youtube-playback-v1", "playback": value}


@router.get("/search-thumbnails/{cache_id}")
def search_thumbnail(cache_id: str):
    _require_enabled()
    if not THUMBNAIL_ID_RE.fullmatch(cache_id):
        raise HTTPException(status_code=404, detail="Unknown search thumbnail")
    root = storage.ensure_layout(DESCRIPTOR.home)["thumbnail_cache"]
    try:
        path = storage.resolve_within(root, cache_id, require_file=True)
    except storage.YouTubeStorageError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    media_type = mimetypes.guess_type(path.name)[0] or "image/jpeg"
    return FileResponse(
        path,
        media_type=media_type,
        headers={
            "Cache-Control": "private, max-age=86400",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/media/{item_id}/{relative_path:path}")
def media(item_id: str, relative_path: str, request: Request):
    _require_enabled()
    item = _item_or_404(item_id)
    allowed = {
        item["video_path"],
        item.get("thumbnail_path"),
        *item.get("audio_paths", []),
        *(entry["path"] for entry in item.get("subtitles", [])),
    }
    if relative_path not in allowed:
        raise HTTPException(status_code=404, detail="Unknown YouTube local asset")
    try:
        path = storage.resolve_within(
            LIBRARY_ROOT, relative_path, require_file=True
        )
    except storage.YouTubeStorageError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    size = path.stat().st_size
    headers = {
        "Accept-Ranges": "bytes",
        "Cache-Control": "private, max-age=3600",
        "X-Content-Type-Options": "nosniff",
    }
    range_header = request.headers.get("range")
    byte_range = serving.parse_range_header(range_header, size)
    if range_header and byte_range is None:
        return Response(
            status_code=416,
            headers={**headers, "Content-Range": f"bytes */{size}"},
        )
    if byte_range is not None:
        start, end = byte_range
        return StreamingResponse(
            serving.file_range_iter(path, start, end),
            status_code=206,
            media_type=media_type,
            headers={
                **headers,
                "Content-Length": str(end - start + 1),
                "Content-Range": f"bytes {start}-{end}/{size}",
            },
        )
    return FileResponse(path, media_type=media_type, headers=headers)
