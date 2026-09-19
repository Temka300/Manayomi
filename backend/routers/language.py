"""HTTP surface for the optional local Languages study library."""
from __future__ import annotations

import json
import mimetypes
import os
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from pydantic import BaseModel, Field

import config
from database import get_user_db
from files_base import index as files_index
from files_base import sources as files_sources
from modules.language import analyzer, anki, catalog, dictionary, library, storage, user_state
from modules.language.imports import LanguageImportError, LanguageImportManager
from services import range_serving, secret_store
import suite_modules


router = APIRouter(prefix="/api/language", tags=["language"])
DESCRIPTOR = config.MODULE_REGISTRY.require("language")
LIBRARY_ROOT = DESCRIPTOR.home / "media" / "library"


class ManualWordPayload(BaseModel):
    lang: str = Field(default="ko", min_length=1, max_length=16)
    headword: str = Field(min_length=1, max_length=300)
    sentence_form: str = Field(default="", max_length=300)
    reading: str = Field(default="", max_length=300)
    deck: str = Field(default="Keivotos", max_length=500)
    sort_index: int | None = None
    senses: list[dict[str, Any]] = Field(default_factory=list, max_length=30)
    examples: list[dict[str, Any]] = Field(default_factory=list, max_length=30)
    notes_text: list[dict[str, Any]] = Field(default_factory=list, max_length=30)
    tags: list[str] = Field(default_factory=list, max_length=100)
    personal_note: str = Field(default="", max_length=20000)


class WordUpdatePayload(BaseModel):
    lang: str | None = Field(default=None, max_length=16)
    headword: str | None = Field(default=None, max_length=300)
    sentence_form: str | None = Field(default=None, max_length=300)
    reading: str | None = Field(default=None, max_length=300)
    deck: str | None = Field(default=None, max_length=500)
    sort_index: int | None = None
    senses: list[dict[str, Any]] | None = Field(default=None, max_length=30)
    examples: list[dict[str, Any]] | None = Field(default=None, max_length=30)
    notes_text: list[dict[str, Any]] | None = Field(default=None, max_length=30)
    tags: list[str] | None = Field(default=None, max_length=100)
    personal_note: str | None = Field(default=None, max_length=20000)


class MediaPayload(BaseModel):
    role: Literal["word_audio", "sentence_audio", "image"]
    filename: str = Field(min_length=1, max_length=240)
    content_base64: str = Field(min_length=1, max_length=45 * 1024 * 1024)


class FavoritePayload(BaseModel):
    favorite: bool


class WordListPayload(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=1000)


class ListMembershipPayload(BaseModel):
    word_ids: list[str] = Field(min_length=1, max_length=5000)
    member: bool = True


class BulkPayload(BaseModel):
    word_ids: list[str] = Field(min_length=1, max_length=5000)
    action: Literal["favorite", "unfavorite", "add_to_list", "remove_from_list"]
    list_id: str | None = Field(default=None, max_length=80)


class PracticeSessionPayload(BaseModel):
    mode: Literal["ko_meaning", "meaning_ko", "audio_meaning", "cloze"]
    word_ids: list[str] = Field(min_length=1, max_length=5000)
    length: int | None = Field(default=20, ge=1, le=5000)


class PracticeAnswerPayload(BaseModel):
    session_id: str = Field(min_length=1, max_length=80)
    word_id: str = Field(min_length=1, max_length=80)
    correct: bool
    finish: bool = False


class LanguageSettingsPayload(BaseModel):
    port: int = Field(default=anki.DEFAULT_PORT, ge=1, le=65535)
    sync_mode: Literal["incremental", "full"] = "incremental"
    api_key: str | None = Field(default=None, max_length=1000)
    clear_api_key: bool = False
    krdict_api_key: str | None = Field(default=None, max_length=1000)
    clear_krdict_api_key: bool = False


class AnalyzerPayload(BaseModel):
    text: str = Field(min_length=1, max_length=analyzer.MAX_TEXT_LENGTH)


class AnalyzerSavePayload(BaseModel):
    analysis_id: str | None = Field(default=None, max_length=80)
    text: str = Field(min_length=1, max_length=analyzer.MAX_TEXT_LENGTH)
    translation_en: str = Field(default="", max_length=20000)
    translation_mn: str = Field(default="", max_length=20000)
    analysis: dict[str, Any]


class DictionaryPayload(BaseModel):
    query: str = Field(min_length=1, max_length=100)


class ProfilePayload(BaseModel):
    mapping: dict[str, Any]


class PreviewPayload(BaseModel):
    deck_pattern: str = Field(min_length=1, max_length=500)


class ImportPayload(BaseModel):
    preview_token: str = Field(min_length=16, max_length=80)
    selection_sha256: str = Field(min_length=64, max_length=64)
    authorized: bool
    merge_manual_ids: list[str] = Field(default_factory=list, max_length=1000)


def _require_enabled() -> None:
    with get_user_db() as connection:
        suite_modules.ensure_schema(connection)
        enabled = suite_modules.enabled_ids(connection)
    if DESCRIPTOR.slug not in enabled:
        raise HTTPException(status_code=409, detail="Languages module is disabled")


def _ensure_foundation() -> dict[str, Path]:
    layout = storage.ensure_layout(DESCRIPTOR.home)
    with catalog.open_catalog(DESCRIPTOR.database):
        pass
    with get_user_db() as connection:
        user_state.ensure_user_schema(connection)
        DESCRIPTOR.publish(connection)
    return layout


def _settings(connection) -> dict[str, Any]:
    user_state.ensure_user_schema(connection)
    row = connection.execute(
        "SELECT port, sync_mode, cached_probe_json, updated_at "
        "FROM language_anki_settings WHERE singleton=1"
    ).fetchone()
    if row is None:
        return {
            "port": anki.DEFAULT_PORT,
            "sync_mode": "incremental",
            "cached_probe": None,
            "updated_at": None,
        }
    return {
        "port": int(row["port"]),
        "sync_mode": str(row["sync_mode"]),
        "cached_probe": (
            json.loads(row["cached_probe_json"])
            if row["cached_probe_json"]
            else None
        ),
        "updated_at": row["updated_at"],
    }


def _api_key() -> tuple[str | None, str]:
    environment = os.environ.get("ANKICONNECT_API_KEY", "").strip()
    if environment:
        return environment, "environment"
    if DESCRIPTOR.credentials is None:
        return None, "none"
    saved = secret_store.load_secret(DESCRIPTOR.credentials, "api_key_dpapi")
    return saved, "saved" if saved else "none"


def _krdict_api_key() -> tuple[str | None, str]:
    environment = os.environ.get("KRDICT_API_KEY", "").strip()
    if environment:
        return environment, "environment"
    if DESCRIPTOR.credentials is None:
        return None, "none"
    saved = secret_store.load_secret(
        DESCRIPTOR.credentials,
        "krdict_api_key_dpapi",
    )
    return saved, "saved" if saved else "none"


def _client() -> anki.AnkiConnectClient:
    with get_user_db() as connection:
        settings = _settings(connection)
    key, _ = _api_key()
    return anki.AnkiConnectClient(
        port=int(settings["port"]),
        api_key=key,
    )


def _publish_and_scan() -> dict[str, Any]:
    with get_user_db() as connection:
        DESCRIPTOR.publish(connection)
        source_id = files_sources.deterministic_source_id(LIBRARY_ROOT)
        source = files_sources.get_source(connection, source_id)
        all_sources = files_sources.list_sources(connection)
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


_IMPORT_MANAGER: LanguageImportManager | None = None


def _manager() -> LanguageImportManager:
    global _IMPORT_MANAGER
    if _IMPORT_MANAGER is None:
        _IMPORT_MANAGER = LanguageImportManager(
            DESCRIPTOR,
            client_factory=_client,
            on_complete=_publish_and_scan,
        )
    return _IMPORT_MANAGER


def _word_or_404(word_id: str) -> dict[str, Any]:
    with (
        catalog.open_catalog(DESCRIPTOR.database) as catalog_connection,
        get_user_db() as user_connection,
    ):
        user_state.ensure_user_schema(user_connection)
        library.reconcile_manual_projections(catalog_connection, user_connection)
        word = library.effective_word(
            catalog_connection,
            user_connection,
            word_id,
        )
    if word is None:
        raise HTTPException(status_code=404, detail="Unknown Languages word")
    return word


@router.get("/status")
def status() -> dict[str, Any]:
    """Return local/cached state only; this endpoint never contacts Anki."""
    _require_enabled()
    layout = _ensure_foundation()
    with (
        catalog.open_catalog(DESCRIPTOR.database) as catalog_connection,
        get_user_db() as user_connection,
    ):
        user_state.ensure_user_schema(user_connection)
        language_settings = _settings(user_connection)
        counts = {
            "words": int(
                catalog_connection.execute(
                    "SELECT COUNT(*) AS count FROM language_words"
                ).fetchone()["count"]
            ),
            "missing": int(
                catalog_connection.execute(
                    "SELECT COUNT(*) AS count FROM language_words WHERE missing<>0"
                ).fetchone()["count"]
            ),
            "manual": int(
                user_connection.execute(
                    "SELECT COUNT(*) AS count FROM language_user_words "
                    "WHERE retired_at IS NULL"
                ).fetchone()["count"]
            ),
            "media": int(
                catalog_connection.execute(
                    "SELECT COUNT(*) AS count FROM language_media WHERE active<>0"
                ).fetchone()["count"]
            ),
            "lists": int(
                user_connection.execute(
                    "SELECT COUNT(*) AS count FROM language_word_lists "
                    "WHERE retired_at IS NULL"
                ).fetchone()["count"]
            ),
            "saved_analyses": int(
                user_connection.execute(
                    "SELECT COUNT(*) AS count FROM language_analyzer_saved "
                    "WHERE retired_at IS NULL"
                ).fetchone()["count"]
            ),
        }
        last_sync = catalog_connection.execute(
            "SELECT run_id, status, counts_json, started_at, finished_at, error "
            "FROM language_sync_runs ORDER BY started_at DESC LIMIT 1"
        ).fetchone()
    _, key_source = _api_key()
    return {
        "format": "keivotos-language-status-v1",
        "enabled": True,
        "counts": counts,
        "storage": {
            **{key: str(value) for key, value in layout.items()},
            "database": str(DESCRIPTOR.database),
            "credentials": str(DESCRIPTOR.credentials),
            "files_source_id": files_sources.deterministic_source_id(LIBRARY_ROOT),
        },
        "anki": {
            "port": language_settings["port"],
            "sync_mode": language_settings["sync_mode"],
            "api_key_source": key_source,
            "cached_probe": language_settings["cached_probe"],
        },
        "last_sync": (
            {
                **dict(last_sync),
                "counts": json.loads(last_sync["counts_json"] or "{}"),
            }
            if last_sync is not None
            else None
        ),
        "jobs": _manager().jobs(),
        "analyzer": analyzer.engine_status(),
    }


@router.get("/analyzer/status")
def analyzer_status() -> dict[str, Any]:
    """Return local engine and saved-history state without network activity."""
    _require_enabled()
    _ensure_foundation()
    with get_user_db() as user_connection:
        user_state.ensure_user_schema(user_connection)
        saved = int(
            user_connection.execute(
                "SELECT COUNT(*) AS count FROM language_analyzer_saved "
                "WHERE retired_at IS NULL"
            ).fetchone()["count"]
        )
    _, dictionary_source = _krdict_api_key()
    return {
        "format": "keivotos-language-analyzer-status-v1",
        **analyzer.engine_status(),
        "saved_analyses": saved,
        "dictionary": {
            "provider": "KRDICT",
            "configured": dictionary_source != "none",
            "key_source": dictionary_source,
            "automatic": False,
        },
    }


@router.post("/analyzer/analyze")
def analyze_text(payload: AnalyzerPayload) -> dict[str, Any]:
    _require_enabled()
    _ensure_foundation()
    try:
        with (
            catalog.open_catalog(DESCRIPTOR.database) as catalog_connection,
            get_user_db() as user_connection,
        ):
            user_state.ensure_user_schema(user_connection)
            result, cached = analyzer.analyze(catalog_connection, payload.text)
            context = library.analyzer_library_context(
                catalog_connection,
                user_connection,
                source_text=result["text"],
                tokens=result["tokens"],
            )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    exact = context.get("exact_example")
    translations = {
        str(value.get("lang") or ""): str(value.get("text") or "")
        for value in (exact or {}).get("translations", [])
        if isinstance(value, dict)
    }
    return {
        **result,
        "cached": cached,
        "library": context,
        "translation": {
            "en": translations.get("en", ""),
            "mn": translations.get("mn", ""),
            "provenance": (exact or {}).get("provenance") if exact else "Your translation",
            "editable": True,
        },
    }


@router.get("/analyzer/history")
def analyzer_history(
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, Any]:
    _require_enabled()
    _ensure_foundation()
    with get_user_db() as user_connection:
        user_state.ensure_user_schema(user_connection)
        items = library.list_saved_analyses(user_connection, limit=limit)
    return {
        "format": "keivotos-language-analyzer-history-v1",
        "items": items,
    }


@router.post("/analyzer/history", status_code=201)
def save_analyzer_history(payload: AnalyzerSavePayload) -> dict[str, Any]:
    _require_enabled()
    _ensure_foundation()
    try:
        with get_user_db() as user_connection:
            user_state.ensure_user_schema(user_connection)
            item = library.save_analysis(
                user_connection,
                source_text=payload.text,
                translation_en=payload.translation_en,
                translation_mn=payload.translation_mn,
                analysis=payload.analysis,
                analysis_id=payload.analysis_id,
            )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "format": "keivotos-language-analyzer-saved-v1",
        "item": item,
    }


@router.delete("/analyzer/history/{analysis_id}")
def retire_analyzer_history(analysis_id: str) -> dict[str, Any]:
    _require_enabled()
    _ensure_foundation()
    try:
        with get_user_db() as user_connection:
            user_state.ensure_user_schema(user_connection)
            library.retire_saved_analysis(user_connection, analysis_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "format": "keivotos-language-analyzer-retired-v1",
        "retired": analysis_id,
    }


@router.post("/analyzer/dictionary")
def dictionary_lookup(payload: DictionaryPayload) -> dict[str, Any]:
    """Run an explicit KRDICT request; this is never called by analysis itself."""
    _require_enabled()
    _ensure_foundation()
    key, _ = _krdict_api_key()
    if not key:
        raise HTTPException(
            status_code=409,
            detail="Save a KRDICT API key in Languages settings first",
        )
    try:
        with catalog.open_catalog(DESCRIPTOR.database) as catalog_connection:
            return dictionary.lookup(
                catalog_connection,
                query=payload.query,
                api_key=key,
                user_agent=DESCRIPTOR.user_agent,
            )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except dictionary.DictionaryLookupError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/words")
def words(
    query: str = Query(default="", max_length=300),
    deck: str = Query(default="", max_length=500),
    tag: str = Query(default="", max_length=200),
    stage: str = Query(default="", max_length=40),
    source: str = Query(default="", max_length=40),
    favorites: bool = False,
    missing: bool | None = None,
    suspended: bool | None = None,
    list_id: str = Query(default="", max_length=80),
    content: Literal["all", "sentences", "grammar"] = Query(default="all"),
    sort: str = Query(default="index", max_length=40),
    descending: bool = False,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=60, ge=1, le=5000),
) -> dict[str, Any]:
    _require_enabled()
    _ensure_foundation()
    with (
        catalog.open_catalog(DESCRIPTOR.database) as catalog_connection,
        get_user_db() as user_connection,
    ):
        user_state.ensure_user_schema(user_connection)
        items, total = library.list_words(
            catalog_connection,
            user_connection,
            query=query,
            deck=deck,
            tag=tag,
            stage=stage,
            source=source,
            favorites=favorites,
            missing=missing,
            suspended=suspended,
            list_id=list_id,
            content=content,
            sort=sort,
            descending=descending,
            offset=offset,
            limit=limit,
        )
    return {
        "format": "keivotos-language-words-v1",
        "items": items,
        "total": total,
        "offset": offset,
        "limit": limit,
    }


@router.get("/words/{word_id}")
def word(word_id: str) -> dict[str, Any]:
    _require_enabled()
    _ensure_foundation()
    return {"format": "keivotos-language-word-v1", "word": _word_or_404(word_id)}


@router.post("/words", status_code=201)
def create_word(payload: ManualWordPayload) -> dict[str, Any]:
    _require_enabled()
    _ensure_foundation()
    try:
        with (
            catalog.open_catalog(DESCRIPTOR.database) as catalog_connection,
            get_user_db() as user_connection,
        ):
            word_id = library.create_manual_word(
                catalog_connection,
                user_connection,
                payload.model_dump(),
            )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"format": "keivotos-language-word-v1", "word": _word_or_404(word_id)}


@router.patch("/words/{word_id}")
def update_word(word_id: str, payload: WordUpdatePayload) -> dict[str, Any]:
    _require_enabled()
    _ensure_foundation()
    try:
        with (
            catalog.open_catalog(DESCRIPTOR.database) as catalog_connection,
            get_user_db() as user_connection,
        ):
            user_state.ensure_user_schema(user_connection)
            library.update_word(
                catalog_connection,
                user_connection,
                word_id,
                payload.model_dump(exclude_unset=True),
            )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"format": "keivotos-language-word-v1", "word": _word_or_404(word_id)}


@router.delete("/words/{word_id}/override")
def revert_word_override(
    word_id: str,
    field: str | None = Query(default=None, max_length=80),
) -> dict[str, Any]:
    _require_enabled()
    _word_or_404(word_id)
    with get_user_db() as connection:
        user_state.ensure_user_schema(connection)
        removed = library.revert_overrides(connection, word_id, field)
    return {
        "format": "keivotos-language-override-v1",
        "removed": removed,
        "word": _word_or_404(word_id),
    }


@router.delete("/words/{word_id}")
def delete_word(word_id: str) -> dict[str, Any]:
    _require_enabled()
    try:
        with (
            catalog.open_catalog(DESCRIPTOR.database) as catalog_connection,
            get_user_db() as user_connection,
        ):
            user_state.ensure_user_schema(user_connection)
            library.retire_manual_word(
                catalog_connection,
                user_connection,
                word_id,
            )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"format": "keivotos-language-retirement-v1", "retired": word_id}


@router.post("/words/{word_id}/media", status_code=201)
def attach_word_media(word_id: str, payload: MediaPayload) -> dict[str, Any]:
    _require_enabled()
    _ensure_foundation()
    try:
        content = library.decode_media_payload(payload.content_base64)
        with (
            catalog.open_catalog(DESCRIPTOR.database) as catalog_connection,
            get_user_db() as user_connection,
        ):
            user_state.ensure_user_schema(user_connection)
            media = library.attach_media(
                catalog_connection,
                user_connection,
                LIBRARY_ROOT,
                word_id=word_id,
                role=payload.role,
                filename=payload.filename,
                payload=content,
            )
        publication = _publish_and_scan()
    except (ValueError, storage.LanguageStorageError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "format": "keivotos-language-media-v1",
        "media": media,
        "publication": publication,
    }


@router.get("/media/{word_id}/{role}")
def serve_word_media(word_id: str, role: str, request: Request):
    _require_enabled()
    with (
        catalog.open_catalog(DESCRIPTOR.database) as catalog_connection,
        get_user_db() as user_connection,
    ):
        user_state.ensure_user_schema(user_connection)
        media = library.media_for_role(
            catalog_connection,
            user_connection,
            word_id,
            role,
        )
    if media is None:
        raise HTTPException(status_code=404, detail="Unknown Languages media")
    try:
        path = storage.resolve_within(
            LIBRARY_ROOT,
            str(media["relative_path"]),
            require_file=True,
        )
    except storage.LanguageStorageError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    digest, size = storage.hash_file(path)
    if digest != media["sha256"] or size != int(media["bytes"]):
        raise HTTPException(status_code=409, detail="Languages media changed on disk")
    media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    headers = {
        "Accept-Ranges": "bytes",
        "Cache-Control": "private, max-age=3600",
        "X-Content-Type-Options": "nosniff",
    }
    range_header = request.headers.get("range")
    byte_range = range_serving.parse_range_header(range_header, size)
    if range_header and byte_range is None:
        return Response(
            status_code=416,
            headers={**headers, "Content-Range": f"bytes */{size}"},
        )
    if byte_range is not None:
        start, end = byte_range
        return StreamingResponse(
            range_serving.file_range_iter(path, start, end),
            status_code=206,
            media_type=media_type,
            headers={
                **headers,
                "Content-Length": str(end - start + 1),
                "Content-Range": f"bytes {start}-{end}/{size}",
            },
        )
    return FileResponse(path, media_type=media_type, headers=headers)


@router.get("/decks")
def decks() -> dict[str, Any]:
    _require_enabled()
    _ensure_foundation()
    with catalog.open_catalog(DESCRIPTOR.database) as connection:
        rows = connection.execute(
            "SELECT deck, COUNT(*) AS words, "
            "SUM(CASE WHEN missing<>0 THEN 1 ELSE 0 END) AS missing "
            "FROM language_words GROUP BY deck ORDER BY deck COLLATE NOCASE"
        ).fetchall()
    return {
        "format": "keivotos-language-decks-v1",
        "items": [dict(row) for row in rows],
    }


@router.get("/today")
def today() -> dict[str, Any]:
    _require_enabled()
    _ensure_foundation()
    with (
        catalog.open_catalog(DESCRIPTOR.database) as catalog_connection,
        get_user_db() as user_connection,
    ):
        user_state.ensure_user_schema(user_connection)
        rows = catalog_connection.execute(
            "SELECT DISTINCT word_id FROM language_progress WHERE due_now<>0"
        ).fetchall()
        items = [
            library.effective_word(
                catalog_connection,
                user_connection,
                str(row["word_id"]),
            )
            for row in rows
        ]
    return {
        "format": "keivotos-language-today-v1",
        "items": [item for item in items if item is not None],
        "cached": True,
    }


@router.get("/favorites")
def favorites() -> dict[str, Any]:
    _require_enabled()
    with get_user_db() as connection:
        user_state.ensure_user_schema(connection)
        word_ids = [
            str(row["word_id"])
            for row in connection.execute(
                "SELECT word_id FROM language_favorites ORDER BY added_at DESC"
            ).fetchall()
        ]
    return {"format": "keivotos-language-favorites-v1", "word_ids": word_ids}


@router.put("/favorites/{word_id}")
def update_favorite(word_id: str, payload: FavoritePayload) -> dict[str, Any]:
    _require_enabled()
    _word_or_404(word_id)
    with get_user_db() as connection:
        favorite = library.set_favorite(connection, word_id, payload.favorite)
    return {"word_id": word_id, "favorite": favorite}


@router.delete("/favorites/{word_id}")
def delete_favorite(word_id: str) -> dict[str, Any]:
    return update_favorite(word_id, FavoritePayload(favorite=False))


@router.get("/lists")
def lists() -> dict[str, Any]:
    _require_enabled()
    with get_user_db() as connection:
        items = library.list_word_lists(connection)
    return {"format": "keivotos-language-lists-v1", "items": items}


@router.post("/lists", status_code=201)
def create_list(payload: WordListPayload) -> dict[str, Any]:
    _require_enabled()
    try:
        with get_user_db() as connection:
            item = library.create_word_list(
                connection,
                payload.name,
                payload.description,
            )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"format": "keivotos-language-list-v1", "item": item}


@router.patch("/lists/{list_id}")
def update_list(list_id: str, payload: WordListPayload) -> dict[str, Any]:
    _require_enabled()
    try:
        with get_user_db() as connection:
            item = library.update_word_list(
                connection,
                list_id,
                name=payload.name,
                description=payload.description,
            )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"format": "keivotos-language-list-v1", "item": item}


@router.delete("/lists/{list_id}")
def delete_list(list_id: str) -> dict[str, Any]:
    _require_enabled()
    try:
        with get_user_db() as connection:
            library.retire_word_list(connection, list_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"format": "keivotos-language-list-retirement-v1", "retired": list_id}


@router.put("/lists/{list_id}/items")
def update_list_items(
    list_id: str,
    payload: ListMembershipPayload,
) -> dict[str, Any]:
    _require_enabled()
    try:
        with get_user_db() as connection:
            changed = library.set_list_membership(
                connection,
                list_id,
                payload.word_ids,
                payload.member,
            )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"list_id": list_id, "changed": changed, "member": payload.member}


@router.post("/bulk")
def bulk(payload: BulkPayload) -> dict[str, Any]:
    _require_enabled()
    with get_user_db() as connection:
        user_state.ensure_user_schema(connection)
        if payload.action in {"favorite", "unfavorite"}:
            for word_id in payload.word_ids:
                library.set_favorite(
                    connection,
                    word_id,
                    payload.action == "favorite",
                )
        else:
            if not payload.list_id:
                raise HTTPException(status_code=400, detail="List id is required")
            try:
                library.set_list_membership(
                    connection,
                    payload.list_id,
                    payload.word_ids,
                    payload.action == "add_to_list",
                )
            except ValueError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "format": "keivotos-language-bulk-v1",
        "action": payload.action,
        "changed": len(set(payload.word_ids)),
    }


@router.post("/practice/session", status_code=201)
def create_practice(payload: PracticeSessionPayload) -> dict[str, Any]:
    _require_enabled()
    try:
        with get_user_db() as connection:
            user_state.ensure_user_schema(connection)
            session = library.create_practice_session(
                connection,
                mode=payload.mode,
                word_ids=payload.word_ids,
                length=payload.length,
            )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"format": "keivotos-language-practice-v1", "session": session}


@router.post("/practice/answer")
def answer_practice(payload: PracticeAnswerPayload) -> dict[str, Any]:
    _require_enabled()
    try:
        with get_user_db() as connection:
            user_state.ensure_user_schema(connection)
            result = library.answer_practice(
                connection,
                session_id=payload.session_id,
                word_id=payload.word_id,
                correct=payload.correct,
                finish=payload.finish,
            )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"format": "keivotos-language-practice-answer-v1", **result}


@router.get("/practice/stats")
def practice_stats() -> dict[str, Any]:
    _require_enabled()
    with get_user_db() as connection:
        user_state.ensure_user_schema(connection)
        stats = library.practice_stats(connection)
    return {"format": "keivotos-language-practice-stats-v1", **stats}


@router.get("/export")
def export_library() -> JSONResponse:
    _require_enabled()
    _ensure_foundation()
    with (
        catalog.open_catalog(DESCRIPTOR.database) as catalog_connection,
        get_user_db() as user_connection,
    ):
        user_state.ensure_user_schema(user_connection)
        payload = library.export_payload(catalog_connection, user_connection)
    return JSONResponse(
        payload,
        headers={
            "Content-Disposition": 'attachment; filename="keivotos-languages.json"',
            "Cache-Control": "no-store",
        },
    )


@router.get("/settings")
def get_settings() -> dict[str, Any]:
    _require_enabled()
    with get_user_db() as connection:
        value = _settings(connection)
    _, source = _api_key()
    _, krdict_source = _krdict_api_key()
    return {
        "format": "keivotos-language-settings-v1",
        **value,
        "has_api_key": source != "none",
        "api_key_source": source,
        "has_krdict_api_key": krdict_source != "none",
        "krdict_api_key_source": krdict_source,
    }


@router.put("/settings")
def put_settings(payload: LanguageSettingsPayload) -> dict[str, Any]:
    _require_enabled()
    with get_user_db() as connection:
        user_state.ensure_user_schema(connection)
        connection.execute(
            "INSERT INTO language_anki_settings(singleton, port, sync_mode, updated_at) "
            "VALUES (1, ?, ?, datetime('now')) ON CONFLICT(singleton) DO UPDATE SET "
            "port=excluded.port, sync_mode=excluded.sync_mode, "
            "updated_at=excluded.updated_at",
            (payload.port, payload.sync_mode),
        )
        connection.commit()
    if DESCRIPTOR.credentials is not None:
        if payload.clear_api_key:
            secret_store.clear_secret_key(
                DESCRIPTOR.credentials,
                "api_key_dpapi",
            )
        elif payload.api_key is not None and payload.api_key.strip():
            secret_store.save_secret(
                DESCRIPTOR.credentials,
                "api_key_dpapi",
                payload.api_key,
                "Keivotos Languages AnkiConnect API key",
            )
        if payload.clear_krdict_api_key:
            secret_store.clear_secret_key(
                DESCRIPTOR.credentials,
                "krdict_api_key_dpapi",
            )
        elif payload.krdict_api_key is not None and payload.krdict_api_key.strip():
            secret_store.save_secret(
                DESCRIPTOR.credentials,
                "krdict_api_key_dpapi",
                payload.krdict_api_key,
                "Keivotos Languages KRDICT API key",
            )
    return get_settings()


@router.get("/profiles")
def profiles() -> dict[str, Any]:
    _require_enabled()
    with get_user_db() as connection:
        user_state.ensure_user_schema(connection)
        items = []
        for row in connection.execute(
            "SELECT note_type, mapping_json, updated_at "
            "FROM language_profiles ORDER BY note_type"
        ).fetchall():
            items.append(
                {
                    "note_type": row["note_type"],
                    "mapping": json.loads(row["mapping_json"]),
                    "updated_at": row["updated_at"],
                }
            )
    return {"format": "keivotos-language-profiles-v1", "items": items}


@router.get("/profiles/{note_type}")
def profile(note_type: str) -> dict[str, Any]:
    _require_enabled()
    with get_user_db() as connection:
        user_state.ensure_user_schema(connection)
        row = connection.execute(
            "SELECT mapping_json, updated_at FROM language_profiles "
            "WHERE note_type=?",
            (note_type,),
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Unknown Languages profile")
    return {
        "format": "keivotos-language-profile-v1",
        "note_type": note_type,
        "mapping": json.loads(row["mapping_json"]),
        "updated_at": row["updated_at"],
    }


@router.put("/profiles/{note_type}")
def put_profile(note_type: str, payload: ProfilePayload) -> dict[str, Any]:
    _require_enabled()
    if not note_type.strip() or len(note_type) > 200:
        raise HTTPException(status_code=400, detail="Invalid note type")
    mapping = dict(payload.mapping)
    mapping["note_type"] = note_type
    if not isinstance(mapping.get("map"), dict):
        raise HTTPException(status_code=400, detail="Profile field map is required")
    with get_user_db() as connection:
        user_state.ensure_user_schema(connection)
        connection.execute(
            "INSERT INTO language_profiles(note_type, mapping_json, updated_at) "
            "VALUES (?, ?, datetime('now')) ON CONFLICT(note_type) DO UPDATE SET "
            "mapping_json=excluded.mapping_json, updated_at=excluded.updated_at",
            (
                note_type,
                json.dumps(mapping, ensure_ascii=False, sort_keys=True),
            ),
        )
        connection.commit()
    return profile(note_type)


@router.get("/anki/probe")
def probe_anki() -> dict[str, Any]:
    _require_enabled()
    try:
        result = _client().probe()
    except anki.AnkiConnectError as exc:
        result = {"reachable": False, "error": str(exc), "decks": []}
    with get_user_db() as connection:
        settings = _settings(connection)
        connection.execute(
            "INSERT INTO language_anki_settings"
            "(singleton, port, sync_mode, cached_probe_json, updated_at) "
            "VALUES (1, ?, ?, ?, datetime('now')) "
            "ON CONFLICT(singleton) DO UPDATE SET "
            "cached_probe_json=excluded.cached_probe_json, "
            "updated_at=excluded.updated_at",
            (
                settings["port"],
                settings["sync_mode"],
                json.dumps(result, ensure_ascii=False, sort_keys=True),
            ),
        )
        connection.commit()
    return {"format": "keivotos-language-anki-probe-v1", **result}


@router.post("/anki/preview")
def preview_anki(payload: PreviewPayload) -> dict[str, Any]:
    _require_enabled()
    try:
        preview = _manager().preview(payload.deck_pattern)
    except (anki.AnkiConnectError, LanguageImportError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"format": "keivotos-language-anki-preview-v1", "preview": preview}


@router.post("/anki/import", status_code=202)
def import_anki(payload: ImportPayload) -> dict[str, Any]:
    _require_enabled()
    try:
        job = _manager().start(
            preview_token=payload.preview_token,
            selection_sha256=payload.selection_sha256,
            authorized=payload.authorized,
            merge_manual_ids=payload.merge_manual_ids,
        )
    except LanguageImportError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"format": "keivotos-language-anki-job-v1", "job": job}


@router.get("/anki/jobs/{job_id}")
def import_job(job_id: str) -> dict[str, Any]:
    _require_enabled()
    job = _manager().get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Unknown Languages import job")
    return {"format": "keivotos-language-anki-job-v1", "job": job}


@router.delete("/anki/jobs/{job_id}")
def cancel_import_job(job_id: str) -> dict[str, Any]:
    _require_enabled()
    try:
        job = _manager().cancel(job_id)
    except LanguageImportError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"format": "keivotos-language-anki-job-v1", "job": job}
