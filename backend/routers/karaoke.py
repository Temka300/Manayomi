"""HTTP surface for the optional local Karaoke library."""
from __future__ import annotations

import base64
import binascii
import hashlib
import mimetypes
from pathlib import Path
import sqlite3
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse, Response, StreamingResponse
from pydantic import BaseModel, Field

import config
from database import get_user_db
from files_base import index as files_index
from files_base import serving, sources as files_sources
from modules.karaoke import catalog, lyrics, storage
from modules.youtube import catalog as youtube_catalog
from modules.youtube import storage as youtube_storage
from modules.karaoke.acquisition import (
    DEFAULT_MAX_BYTES,
    KaraokeAcquisitionError,
    KaraokeAcquisitionManager,
    MIN_FREE_BYTES,
)
from modules.karaoke.kara_moe import KaraMoeError
import suite_modules


router = APIRouter(prefix="/api/karaoke", tags=["karaoke"])
DESCRIPTOR = config.MODULE_REGISTRY.require("karaoke")
LIBRARY_ROOT = DESCRIPTOR.home / "media" / "library"


class FavoritePayload(BaseModel):
    favorite: bool


class PlaylistPayload(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=500)


class PlaylistItemPayload(BaseModel):
    item_id: str = Field(min_length=1, max_length=160)


class PlaylistOrderPayload(BaseModel):
    item_ids: list[str] = Field(min_length=0, max_length=500)


class PlaybackPayload(BaseModel):
    position_seconds: float = Field(default=0, ge=0)
    duration_seconds: float | None = Field(default=None, ge=0)
    completed: bool = False
    lyric_id: str | None = Field(default=None, max_length=180)
    lyric_offset_seconds: float = Field(default=0, ge=-30, le=30)
    repeat_mode: Literal["off", "all", "one"] = "off"
    shuffle: bool = False


class KaraMoePlanPayload(BaseModel):
    provider_id: str = Field(min_length=1, max_length=80)
    max_bytes: int = Field(default=DEFAULT_MAX_BYTES, gt=0, le=20 * 1024 * 1024 * 1024)


class KaraMoeDownloadPayload(BaseModel):
    plan_token: str = Field(min_length=32, max_length=64)
    selection_sha256: str = Field(min_length=64, max_length=64)
    authorized: bool


class SubtitleUploadPayload(BaseModel):
    filename: str = Field(min_length=1, max_length=180)
    content_base64: str = Field(min_length=1, max_length=8 * 1024 * 1024)
    label: str = Field(default="", max_length=120)
    language: str = Field(default="", max_length=40)


class FilesImportPayload(BaseModel):
    source_id: str = Field(min_length=1, max_length=80)
    relative_path: str = Field(min_length=1, max_length=2000)
    title: str = Field(default="", max_length=200)
    subtitle: str = Field(default="", max_length=200)


def _require_enabled() -> None:
    with get_user_db() as connection:
        suite_modules.ensure_schema(connection)
        enabled = suite_modules.enabled_ids(connection)
    if DESCRIPTOR.slug not in enabled:
        raise HTTPException(status_code=409, detail="Karaoke module is disabled")


def _item_or_404(item_id: str) -> dict[str, Any]:
    with catalog.open_catalog(DESCRIPTOR.database) as connection:
        item = catalog.get_item(connection, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Unknown karaoke item")
    with get_user_db() as user_connection:
        item["favorite"] = item_id in catalog.favorite_ids(user_connection)
        item["playback"] = catalog.playback_state(user_connection, item_id)
    item["files_source_id"] = (
        item.get("external_source_id")
        or files_sources.deterministic_source_id(LIBRARY_ROOT)
    )
    item["files_relative_path"] = (
        item.get("external_relative_path") or item["primary_video"]
    )
    item["media_health"] = _media_health(item)
    return item


def _media_health(item: dict[str, Any]) -> dict[str, Any]:
    if item.get("provider") != "kara-moe":
        return {
            "status": "unchecked",
            "actual_bytes": None,
            "expected_bytes": None,
            "can_update": False,
            "obsolete_primary_video": None,
        }
    metadata = item.get("metadata")
    obsolete = None
    if isinstance(metadata, dict):
        keivotos = metadata.get("_keivotos")
        if isinstance(keivotos, dict):
            obsolete = keivotos.get("obsolete_primary_video")
    try:
        path = storage.resolve_within(
            LIBRARY_ROOT, item["primary_video"], require_file=True
        )
        integrity = storage.mp4_integrity(path)
        actual = int(integrity["actual_bytes"])
        expected = integrity.get("expected_bytes")
    except (OSError, storage.KaraokeStorageError):
        actual = None
        expected = None
        integrity = None
    if actual is None:
        status_value = "missing"
    elif integrity is not None and not integrity["complete"]:
        status_value = "incomplete"
    else:
        status_value = "valid"
    return {
        "status": status_value,
        "actual_bytes": actual,
        "expected_bytes": expected,
        "can_update": True,
        "obsolete_primary_video": obsolete,
    }


def _registered_file(source_id: str, relative_path: str) -> tuple[Any, Path]:
    with get_user_db() as user_connection:
        files_sources.ensure_sources_schema(user_connection)
        source = files_sources.get_source(user_connection, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Unknown Files source")
    try:
        resolved = serving.resolve_served_file(source.path, relative_path, [])
    except serving.ServeDenied as denied:
        raise HTTPException(
            status_code=denied.status_code, detail=denied.detail
        ) from denied
    return source, resolved


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


_ACQUISITION_MANAGER: KaraokeAcquisitionManager | None = None


def _acquisition_manager() -> KaraokeAcquisitionManager:
    global _ACQUISITION_MANAGER
    if _ACQUISITION_MANAGER is None:
        _ACQUISITION_MANAGER = KaraokeAcquisitionManager(
            DESCRIPTOR,
            on_complete=_publish_library,
        )
    return _ACQUISITION_MANAGER


@router.get("/status")
def status() -> dict[str, Any]:
    _require_enabled()
    storage.ensure_layout(DESCRIPTOR.home)
    with catalog.open_catalog(DESCRIPTOR.database) as connection:
        count = connection.execute(
            "SELECT COUNT(*) AS count FROM karaoke_items"
        ).fetchone()["count"]
    with get_user_db() as user_connection:
        catalog.ensure_user_schema(user_connection)
        playlists = len(catalog.list_playlists(user_connection))
    return {
        "format": "keivotos-karaoke-status-v1",
        "initialized": True,
        "items": count,
        "playlists": playlists,
        "storage": {
            "home": str(DESCRIPTOR.home),
            "library": str(LIBRARY_ROOT),
            "database": str(DESCRIPTOR.database),
        },
        "providers": {"kara_moe": True, "youtube_handoff": True},
        "limits": {
            "max_file_bytes": DEFAULT_MAX_BYTES,
            "minimum_free_bytes": MIN_FREE_BYTES,
            "active_jobs": 1,
            "search_results": 50,
        },
        "jobs": _acquisition_manager().jobs(),
    }


@router.get("/kara-moe/search")
def kara_moe_search(
    query: str = Query(min_length=1, max_length=200),
    limit: int = Query(default=20, ge=1, le=50),
) -> dict[str, Any]:
    _require_enabled()
    try:
        items = _acquisition_manager().search(query, limit)
    except (KaraMoeError, OSError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "format": "keivotos-kara-moe-search-v1",
        "query": query,
        "items": items,
    }


@router.get("/kara-moe/{provider_id}")
def kara_moe_detail(provider_id: str) -> dict[str, Any]:
    _require_enabled()
    try:
        item = _acquisition_manager().detail(provider_id)
    except (KaraMoeError, OSError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"format": "keivotos-kara-moe-detail-v1", "item": item}


@router.post("/kara-moe/plan")
def kara_moe_plan(payload: KaraMoePlanPayload) -> dict[str, Any]:
    _require_enabled()
    try:
        plan = _acquisition_manager().plan(
            payload.provider_id,
            max_bytes=payload.max_bytes,
        )
    except (KaraMoeError, OSError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"format": "keivotos-kara-moe-plan-v1", "plan": plan}


@router.post("/kara-moe/download", status_code=202)
def kara_moe_download(payload: KaraMoeDownloadPayload) -> dict[str, Any]:
    _require_enabled()
    try:
        job = _acquisition_manager().start(
            token=payload.plan_token,
            selection_sha256=payload.selection_sha256,
            authorized=payload.authorized,
        )
    except KaraokeAcquisitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"format": "keivotos-karaoke-job-v1", "job": job}


@router.get("/jobs")
def acquisition_jobs() -> dict[str, Any]:
    _require_enabled()
    return {
        "format": "keivotos-karaoke-jobs-v1",
        "jobs": _acquisition_manager().jobs(),
    }


@router.get("/jobs/{job_id}")
def acquisition_job(job_id: str) -> dict[str, Any]:
    _require_enabled()
    try:
        job = _acquisition_manager().job(job_id)
    except KaraokeAcquisitionError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"format": "keivotos-karaoke-job-v1", "job": job}


@router.post("/jobs/{job_id}/cancel")
def cancel_acquisition_job(job_id: str) -> dict[str, Any]:
    _require_enabled()
    try:
        job = _acquisition_manager().cancel(job_id)
    except KaraokeAcquisitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"format": "keivotos-karaoke-job-v1", "job": job}


@router.post("/jobs/{job_id}/resume", status_code=202)
def resume_acquisition_job(job_id: str) -> dict[str, Any]:
    _require_enabled()
    try:
        job = _acquisition_manager().resume(job_id)
    except KaraokeAcquisitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"format": "keivotos-karaoke-job-v1", "job": job}


@router.get("/library")
def library(
    query: str = Query(default="", max_length=200),
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    favorites_only: bool = Query(default=False),
) -> dict[str, Any]:
    _require_enabled()
    with catalog.open_catalog(DESCRIPTOR.database) as connection:
        items = catalog.list_items(
            connection, query=query, limit=limit, offset=offset
        )
    with get_user_db() as user_connection:
        favorites = catalog.favorite_ids(user_connection)
        for item in items:
            item["favorite"] = item["item_id"] in favorites
            item["playback"] = catalog.playback_state(
                user_connection, item["item_id"]
            )
            item["files_source_id"] = (
                item.get("external_source_id")
                or files_sources.deterministic_source_id(LIBRARY_ROOT)
            )
            item["files_relative_path"] = (
                item.get("external_relative_path") or item["primary_video"]
            )
            item["media_health"] = _media_health(item)
    if favorites_only:
        items = [item for item in items if item["favorite"]]
    return {"format": "keivotos-karaoke-library-v1", "items": items}


@router.get("/library/{item_id}")
def library_item(item_id: str) -> dict[str, Any]:
    _require_enabled()
    return {
        "format": "keivotos-karaoke-item-v1",
        "item": _item_or_404(item_id),
    }


@router.post("/library/import-files")
def import_files_asset(payload: FilesImportPayload) -> dict[str, Any]:
    _require_enabled()
    source, resolved = _registered_file(payload.source_id, payload.relative_path)
    if resolved.suffix.casefold() not in storage.SAFE_MEDIA_SUFFIXES:
        raise HTTPException(
            status_code=400,
            detail="Karaoke imports require a supported local audio/video file",
        )
    digest, byte_size = storage.hash_file(resolved)
    item_id = f"files:{digest}"
    with catalog.open_catalog(DESCRIPTOR.database) as connection:
        existing = catalog.get_item(connection, item_id)
    if existing is not None:
        return {
            "format": "keivotos-karaoke-item-v1",
            "item": _item_or_404(item_id),
            "already_imported": True,
        }
    layout = storage.ensure_layout(DESCRIPTOR.home)
    title = payload.title.strip() or resolved.stem
    directory = layout["library"] / storage.item_directory_name(
        digest[:16], title
    )
    if directory.exists():
        raise HTTPException(status_code=409, detail="Karaoke import already exists")
    directory.mkdir(parents=True)
    try:
        metadata = {
            "provider": "files",
            "source_id": source.source_id,
            "source_display_name": source.display_name,
            "source_role": source.role,
            "relative_path": payload.relative_path,
            "original_name": resolved.name,
            "byte_size": byte_size,
            "sha256": digest,
        }
        storage.write_json_create(directory / "source.metadata.json", metadata)
        storage.write_json_create(
            directory / "acquisition.receipt.json",
            {
                "format": "keivotos-karaoke-files-import-receipt-v1",
                "mode": "reference",
                "source_id": source.source_id,
                "relative_path": payload.relative_path,
                "sha256": digest,
                "bytes": byte_size,
            },
        )
    except Exception:
        # The directory contains only create-in-progress metadata. Preserve it
        # for diagnosis instead of deleting or rewriting user evidence.
        raise
    relative_directory = directory.relative_to(LIBRARY_ROOT).as_posix()
    item = {
        "item_id": item_id,
        "provider": "files",
        "provider_id": digest,
        "title": title,
        "subtitle": payload.subtitle.strip() or f"From {source.display_name}",
        "year": None,
        "duration": None,
        "primary_video": payload.relative_path.replace("\\", "/"),
        "thumbnail": None,
        "metadata_path": f"{relative_directory}/source.metadata.json",
        "receipt_path": f"{relative_directory}/acquisition.receipt.json",
        "primary_sha256": digest,
        "external_source_id": source.source_id,
        "external_relative_path": payload.relative_path.replace("\\", "/"),
        "metadata": metadata,
    }
    with catalog.open_catalog(DESCRIPTOR.database) as connection:
        catalog.upsert_item(connection, item, {"source": [source.display_name]}, [])
    _publish_library()
    return {
        "format": "keivotos-karaoke-item-v1",
        "item": _item_or_404(item_id),
        "already_imported": False,
    }


@router.post("/library/import-youtube/{youtube_item_id}")
def import_youtube_item(youtube_item_id: str) -> dict[str, Any]:
    """Hand a local YouTube item and its captions to Karaoke server-side."""
    _require_enabled()
    youtube_descriptor = config.MODULE_REGISTRY.require("youtube")
    youtube_root = youtube_descriptor.home / "media" / "library"
    with youtube_catalog.open_catalog(
        youtube_descriptor.database
    ) as connection:
        youtube_item = youtube_catalog.get_item(connection, youtube_item_id)
    if youtube_item is None:
        raise HTTPException(
            status_code=404, detail="Unknown YouTube library item"
        )
    imported = import_files_asset(
        FilesImportPayload(
            source_id=files_sources.deterministic_source_id(youtube_root),
            relative_path=youtube_item["video_path"],
            title=youtube_item["title"],
            subtitle=(
                f"From {youtube_item['channel']}"
                if youtube_item.get("channel")
                else "From YouTube downloads"
            ),
        )
    )
    karaoke_item_id = imported["item"]["item_id"]
    existing_names = {
        Path(track["relative_path"]).name.casefold()
        for track in imported["item"].get("lyrics", [])
    }
    attached = 0
    skipped = 0
    for track in youtube_item.get("subtitles", []):
        try:
            source_path = youtube_storage.resolve_within(
                youtube_root, track["path"], require_file=True
            )
        except youtube_storage.YouTubeStorageError:
            skipped += 1
            continue
        filename = source_path.name
        normalized_name = (
            storage.safe_name(Path(filename).stem, "lyrics", 120)
            + source_path.suffix.casefold()
        ).casefold()
        if normalized_name in existing_names:
            skipped += 1
            continue
        data = source_path.read_bytes()
        if len(data) > 5 * 1024 * 1024:
            skipped += 1
            continue
        language_parts = filename.split(".")
        language = (
            language_parts[-2] if len(language_parts) > 2 else ""
        )
        attach_lyrics(
            karaoke_item_id,
            SubtitleUploadPayload(
                filename=filename,
                content_base64=base64.b64encode(data).decode("ascii"),
                label=(
                    "YouTube automatic captions"
                    if track.get("automatic")
                    else "YouTube subtitles"
                ),
                language=language,
            ),
        )
        existing_names.add(normalized_name)
        attached += 1
    return {
        "format": "keivotos-karaoke-youtube-handoff-v1",
        "item": _item_or_404(karaoke_item_id),
        "already_imported": imported["already_imported"],
        "subtitles_attached": attached,
        "subtitles_skipped": skipped,
    }


@router.post("/library/{item_id}/lyrics")
def attach_lyrics(
    item_id: str, payload: SubtitleUploadPayload
) -> dict[str, Any]:
    _require_enabled()
    item = _item_or_404(item_id)
    suffix = Path(payload.filename).suffix.casefold()
    if suffix not in storage.SAFE_SUBTITLE_SUFFIXES:
        raise HTTPException(
            status_code=400,
            detail="Lyrics must be ASS, SSA, SRT, VTT, or LRC",
        )
    try:
        data = base64.b64decode(payload.content_base64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(status_code=400, detail="Invalid subtitle data") from exc
    if len(data) > 5 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Subtitle exceeds 5 MiB")
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise HTTPException(
            status_code=400, detail="Subtitle must be UTF-8 text"
        ) from exc
    relative_parent = Path(item["metadata_path"]).parent
    filename = storage.safe_name(
        Path(payload.filename).stem,
        "lyrics",
        120,
    ) + suffix
    relative_path = (relative_parent / filename).as_posix()
    destination = storage.resolve_within(LIBRARY_ROOT, relative_path)
    try:
        digest, _ = storage.write_bytes_create(
            destination, data, 5 * 1024 * 1024
        )
    except storage.KaraokeStorageError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    cues = lyrics.parse_subtitle_text(text, suffix)
    lyric_id = f"{item_id}:user:{hashlib.sha256(relative_path.encode()).hexdigest()[:16]}"
    lyric = {
        "lyric_id": lyric_id,
        "label": payload.label.strip() or Path(filename).stem,
        "language": payload.language.strip(),
        "format": suffix.lstrip("."),
        "source_kind": "user-supplied",
        "relative_path": relative_path,
        "sha256": digest,
        "cues": cues,
    }
    try:
        with catalog.open_catalog(DESCRIPTOR.database) as connection:
            catalog.add_lyric(connection, item_id=item_id, lyric=lyric)
    except (ValueError, sqlite3.IntegrityError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    _publish_library()
    return {
        "format": "keivotos-karaoke-lyrics-v1",
        "lyrics": lyric,
        "item": _item_or_404(item_id),
    }


@router.post("/library/{item_id}/favorite")
def favorite(item_id: str, payload: FavoritePayload) -> dict[str, Any]:
    _require_enabled()
    item = _item_or_404(item_id)
    with get_user_db() as user_connection:
        value = catalog.set_favorite(
            user_connection,
            item_id,
            item.get("primary_sha256"),
            payload.favorite,
        )
    return {"item_id": item_id, "favorite": value}


@router.get("/playlists")
def playlists() -> dict[str, Any]:
    _require_enabled()
    with get_user_db() as user_connection:
        values = catalog.list_playlists(user_connection)
    return {"format": "keivotos-karaoke-playlists-v1", "playlists": values}


@router.post("/playlists")
def create_playlist(payload: PlaylistPayload) -> dict[str, Any]:
    _require_enabled()
    try:
        with get_user_db() as user_connection:
            value = catalog.create_playlist(
                user_connection, payload.name, payload.description
            )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"format": "keivotos-karaoke-playlist-v1", "playlist": value}


@router.put("/playlists/{playlist_id}")
def update_playlist(
    playlist_id: int, payload: PlaylistPayload
) -> dict[str, Any]:
    _require_enabled()
    try:
        with get_user_db() as user_connection:
            value = catalog.update_playlist(
                user_connection,
                playlist_id,
                payload.name,
                payload.description,
            )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"format": "keivotos-karaoke-playlist-v1", "playlist": value}


@router.delete("/playlists/{playlist_id}")
def delete_playlist(playlist_id: int) -> dict[str, Any]:
    _require_enabled()
    with get_user_db() as user_connection:
        deleted = catalog.delete_playlist(user_connection, playlist_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Unknown playlist")
    return {
        "format": "keivotos-karaoke-playlist-delete-v1",
        "playlist_id": playlist_id,
        "deleted": True,
    }


@router.post("/playlists/{playlist_id}/items")
def add_playlist_item(
    playlist_id: int, payload: PlaylistItemPayload
) -> dict[str, Any]:
    _require_enabled()
    item = _item_or_404(payload.item_id)
    try:
        with get_user_db() as user_connection:
            catalog.add_playlist_item(
                user_connection,
                playlist_id,
                payload.item_id,
                item.get("primary_sha256"),
            )
            values = catalog.list_playlists(user_connection)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "format": "keivotos-karaoke-playlist-v1",
        "playlist": next(
            value for value in values if value["playlist_id"] == playlist_id
        ),
    }


@router.delete("/playlists/{playlist_id}/items/{item_id}")
def remove_playlist_item(playlist_id: int, item_id: str) -> dict[str, Any]:
    _require_enabled()
    try:
        with get_user_db() as user_connection:
            value = catalog.remove_playlist_item(
                user_connection, playlist_id, item_id
            )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"format": "keivotos-karaoke-playlist-v1", "playlist": value}


@router.put("/playlists/{playlist_id}/items")
def reorder_playlist_items(
    playlist_id: int, payload: PlaylistOrderPayload
) -> dict[str, Any]:
    _require_enabled()
    try:
        with get_user_db() as user_connection:
            value = catalog.reorder_playlist_items(
                user_connection, playlist_id, payload.item_ids
            )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"format": "keivotos-karaoke-playlist-v1", "playlist": value}


@router.get("/library/{item_id}/playback")
def get_playback(item_id: str) -> dict[str, Any]:
    _require_enabled()
    _item_or_404(item_id)
    with get_user_db() as user_connection:
        value = catalog.playback_state(user_connection, item_id)
    return {"format": "keivotos-karaoke-playback-v1", "playback": value}


@router.put("/library/{item_id}/playback")
def put_playback(item_id: str, payload: PlaybackPayload) -> dict[str, Any]:
    _require_enabled()
    item = _item_or_404(item_id)
    values = payload.model_dump()
    values["file_sha256"] = item.get("primary_sha256")
    with get_user_db() as user_connection:
        value = catalog.save_playback_state(user_connection, item_id, values)
    return {"format": "keivotos-karaoke-playback-v1", "playback": value}


@router.post("/library/{item_id}/play")
def record_play(item_id: str) -> dict[str, Any]:
    _require_enabled()
    item = _item_or_404(item_id)
    with get_user_db() as user_connection:
        value = catalog.record_play(
            user_connection, item_id, item.get("primary_sha256")
        )
    return {"format": "keivotos-karaoke-playback-v1", "playback": value}


def _asset_path(item: dict[str, Any], relative_path: str) -> Path:
    if (
        item.get("external_source_id")
        and relative_path == item.get("external_relative_path")
    ):
        _, path = _registered_file(
            item["external_source_id"], item["external_relative_path"]
        )
        if storage.hash_file(path)[0] != item["primary_sha256"]:
            raise HTTPException(
                status_code=409,
                detail="Referenced Files asset changed since it was added to Karaoke",
            )
        return path
    try:
        return storage.resolve_within(
            LIBRARY_ROOT,
            relative_path,
            require_file=True,
        )
    except storage.KaraokeStorageError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/library/{item_id}/lyrics/{lyric_id}/captions.vtt")
def normalized_captions(item_id: str, lyric_id: str) -> Response:
    """Render normalized cue text without rewriting preserved subtitle files."""
    _require_enabled()
    item = _item_or_404(item_id)
    track = next(
        (
            value
            for value in item.get("lyrics", [])
            if value.get("lyric_id") == lyric_id
        ),
        None,
    )
    if track is None:
        raise HTTPException(status_code=404, detail="Unknown Karaoke lyric track")
    cues = track.get("cues")
    if not isinstance(cues, list) or not cues:
        raise HTTPException(
            status_code=404, detail="Karaoke lyric track has no timed cues"
        )
    return Response(
        content=lyrics.to_webvtt(cues),
        media_type="text/vtt; charset=utf-8",
        headers={
            "Cache-Control": "private, max-age=3600",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/media/{item_id}/{relative_path:path}")
def media(item_id: str, relative_path: str, request: Request):
    _require_enabled()
    item = _item_or_404(item_id)
    allowed = {
        item["primary_video"],
        item.get("thumbnail"),
        *(track["relative_path"] for track in item.get("lyrics", [])),
    }
    if relative_path not in allowed:
        raise HTTPException(status_code=404, detail="Unknown karaoke asset")
    path = _asset_path(item, relative_path)
    size = path.stat().st_size
    media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
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
