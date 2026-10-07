"""Manayomi manga module API. Explicit imports only — no core facade."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import BaseModel, Field
from files_base.sources import deterministic_source_id

import re
import time

from manga import downloader, jobs, mangadex, nhentai
from manga import queries
from manga import roots as manga_roots
from manga import scanner
from manga.browse_paging import browse_window, exact_total, logical_page_count
from manga.covers import cover_path, generate_cover_from_cbz
from manga.database import index_session, remote_gallery_id
from manga.paths import MANGA_MODULE_HOME
from manga.reader_pages import archive_pages, read_page
from manga.search import parse_library_query
from manga.settings import get_manga_settings, update_manga_settings
from product import MANGA_MODULE_NAME, SUITE_NAME, VERSION
from config import MODULE_REGISTRY
from database import get_user_db
import suite_modules


def _require_enabled() -> None:
    with get_user_db() as connection:
        suite_modules.ensure_schema(connection)
        enabled = suite_modules.enabled_ids(connection)
    if "manayomi" not in enabled:
        raise HTTPException(status_code=409, detail="Manayomi module is disabled")


router = APIRouter(dependencies=[Depends(_require_enabled)])


class MangaSettingsUpdate(BaseModel):
    nhentai_enabled: bool | None = None
    cf_clearance: str | None = None
    user_agent: str | None = None
    request_delay_ms: int | None = None
    blur_covers: bool | None = None
    show_ignored: bool | None = None
    cover_progress: str | None = None
    ignored_tags: list[str] | None = None


class RootCreate(BaseModel):
    path: str


class DownloadedIdsImport(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    content: str = Field(max_length=8_000_000)


class RootRelocate(BaseModel):
    path: str
    confirm: bool = False


class ReadingProgressUpdate(BaseModel):
    title: str
    cover_path: str | None = None
    page: int = 0
    page_count: int = 0


@router.get("/api/manga/status")
def manga_status() -> dict[str, Any]:
    with index_session() as index:
        manga_count = index.execute("SELECT COUNT(*) FROM manga").fetchone()[0]
        tag_count = index.execute("SELECT COUNT(*) FROM tags").fetchone()[0]
    settings = get_manga_settings()
    target_root = manga_roots.download_root()
    return {
        "suite": SUITE_NAME,
        "module": MANGA_MODULE_NAME,
        "version": VERSION,
        "module_home": str(MANGA_MODULE_HOME),
        "default_library": str(target_root["path"]) if target_root else "",
        "manga_count": manga_count,
        "tag_count": tag_count,
        "nhentai_enabled": settings["nhentai_enabled"],
    }


@router.get("/api/manga/settings")
def read_manga_settings() -> dict[str, Any]:
    return get_manga_settings()


@router.put("/api/manga/settings")
def write_manga_settings(update: MangaSettingsUpdate) -> dict[str, Any]:
    changes = update.model_dump(exclude_none=True)
    return update_manga_settings(changes)


@router.get("/api/manga/downloaded-ids/export", response_class=PlainTextResponse)
def export_manga_downloaded_ids() -> Response:
    try:
        content = queries.export_downloaded_ids()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return PlainTextResponse(
        content=content,
        headers={"Content-Disposition": 'attachment; filename="manayomi-downloaded-ids.txt"'},
    )


@router.get("/api/manga/downloaded-ids")
def read_manga_downloaded_id_lists() -> dict[str, Any]:
    return {"lists": queries.list_downloaded_id_lists()}


@router.post("/api/manga/downloaded-ids")
def import_manga_downloaded_ids(body: DownloadedIdsImport) -> dict[str, Any]:
    try:
        queries.import_downloaded_ids(body.filename, body.content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return read_manga_downloaded_id_lists()


@router.delete("/api/manga/downloaded-ids/{list_id}")
def remove_manga_downloaded_id_list(list_id: int) -> dict[str, Any]:
    if not queries.remove_downloaded_id_list(list_id):
        raise HTTPException(status_code=404, detail="Downloaded-ID list not found")
    return read_manga_downloaded_id_lists()


@router.get("/api/manga/roots")
def list_manga_roots() -> dict[str, Any]:
    manga_roots.ensure_default_root()
    return {"roots": manga_roots.list_roots()}


@router.post("/api/manga/roots")
def add_manga_root(body: RootCreate) -> dict[str, Any]:
    result = manga_roots.add_root(body.path)
    if not result.get("ok"):
        raise HTTPException(400, result.get("error", "Could not add folder"))
    return result


@router.post("/api/manga/roots/{root_id}/relocate-preview")
def preview_manga_root_relocation(root_id: int, body: RootRelocate) -> dict[str, Any]:
    try:
        return manga_roots.preview_relocation(root_id, body.path)
    except manga_roots.RootRelocationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/api/manga/roots/{root_id}/relocate")
def relocate_manga_root(root_id: int, body: RootRelocate) -> dict[str, Any]:
    if not body.confirm:
        raise HTTPException(status_code=400, detail="Relocation requires an explicit preview and confirmation")
    try:
        result = manga_roots.relocate_root(root_id, body.path)
    except manga_roots.RootRelocationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    with get_user_db() as connection:
        MODULE_REGISTRY.require("manayomi").publish(connection)
    return result


@router.delete("/api/manga/roots/{root_id}")
def remove_manga_root(root_id: int) -> dict[str, Any]:
    if manga_roots.get_root(root_id) is None:
        raise HTTPException(404, "Root not found")
    manga_roots.remove_root(root_id)
    return {"ok": True}


# ---- Library ----

@router.get("/api/manga/library")
def search_manga_library(
    q: str = "",
    page: int = 1,
    per_page: int = 60,
    sort: str = "recent",
    language: str = "all",
    favorites: bool = False,
    category: int | None = None,
) -> dict[str, Any]:
    parsed = parse_library_query(q)
    manga_settings = get_manga_settings()
    result = queries.search_library(
        parsed,
        page=page,
        per_page=per_page,
        sort=sort,
        language=language,
        favorites_only=favorites,
        category_id=category,
        ignored_tags=manga_settings["ignored_tags"],
        show_ignored=manga_settings["show_ignored"],
    )
    result["stats"] = queries.library_stats()
    return result


@router.get("/api/manga/detail/{manga_id}")
def manga_detail(manga_id: int) -> dict[str, Any]:
    detail = queries.get_manga_by_id(manga_id)
    if detail is None:
        raise HTTPException(404, "Manga not found")
    detail["category_ids"] = queries.category_ids_for_gallery(detail["gallery_id"], detail["source"])
    detail["files_source_id"] = None
    detail["files_relative_path"] = None
    root = manga_roots.get_root(detail["root_id"]) if detail.get("root_id") is not None else None
    if root is not None:
        resolved_root = Path(str(root["path"])).expanduser().resolve(strict=False)
        resolved_file = Path(str(detail["file_path"])).expanduser().resolve(strict=False)
        try:
            relative = resolved_file.relative_to(resolved_root)
        except ValueError:
            relative = None
        if relative is not None:
            detail["files_source_id"] = deterministic_source_id(resolved_root)
            detail["files_relative_path"] = relative.as_posix()
    return detail


@router.get("/api/manga/cover/{gallery_id}")
def manga_cover(gallery_id: int) -> Response:
    source = queries.source_for_gallery_id(gallery_id)
    info = queries.cover_info_for_gallery(gallery_id, source)
    if info is None:
        raise HTTPException(404, "Not in library")
    path = cover_path(gallery_id)
    if not path.is_file():
        generated = generate_cover_from_cbz(gallery_id, info["file_path"])
        if generated is None:
            raise HTTPException(404, "No cover available")
    return FileResponse(path, media_type="image/webp", headers={"Cache-Control": "public, max-age=86400"})


@router.get("/api/manga/pages/{gallery_id}")
def manga_page_list(gallery_id: int) -> dict[str, Any]:
    file_path = queries.file_path_for_gallery(
        gallery_id, queries.source_for_gallery_id(gallery_id)
    )
    if file_path is None:
        raise HTTPException(404, "Not in library")
    try:
        version, names = archive_pages(file_path)
    except Exception as exc:  # noqa: BLE001 - unreadable archive is a client-visible error
        raise HTTPException(500, f"Could not read CBZ: {exc}") from exc
    return {"gallery_id": gallery_id, "pages": len(names), "names": list(names), "version": version}


@router.get("/api/manga/page/{gallery_id}/{number}")
def manga_page(
    gallery_id: int,
    number: int,
    max_width: int = 0,
    v: str | None = None,
) -> Response:
    file_path = queries.file_path_for_gallery(
        gallery_id, queries.source_for_gallery_id(gallery_id)
    )
    if file_path is None:
        raise HTTPException(404, "Not in library")
    try:
        data, media_type, version, _ = read_page(file_path, number, max_width=max_width)
    except IndexError as exc:
        raise HTTPException(404, "Page out of range") from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(500, f"Could not read CBZ: {exc}") from exc
    versioned = v == version
    cache_control = "public, max-age=31536000, immutable" if versioned else "public, max-age=86400"
    return Response(
        content=data,
        media_type=media_type,
        headers={
            "Cache-Control": cache_control,
            "ETag": f'"{version}-{number}-{max_width}"',
        },
    )


# ---- Scan ----

class ScanRequest(BaseModel):
    root_id: int
    enrich: bool = True


@router.post("/api/manga/scan")
def start_manga_scan(body: ScanRequest) -> dict[str, Any]:
    if manga_roots.get_root(body.root_id) is None:
        raise HTTPException(404, "Root not found")
    started = scanner.start_scan(body.root_id, body.enrich)
    if not started:
        raise HTTPException(409, "A scan is already running")
    return {"ok": True}


@router.get("/api/manga/scan")
def manga_scan_progress() -> dict[str, Any]:
    return scanner.scan_progress()


# ---- Tags ----

@router.get("/api/manga/tags/top")
def manga_top_tags(limit: int = 60) -> dict[str, Any]:
    return {"tags": queries.top_tags(limit)}


@router.get("/api/manga/tags/suggest")
def manga_suggest_tags(q: str = "", limit: int = 12) -> dict[str, Any]:
    if not q.strip():
        return {"tags": []}
    return {"tags": queries.suggest_tags(q.strip(), limit)}


@router.get("/api/manga/heh/tags")
def heh_tag_directory(sort: str = "popular") -> dict[str, Any]:
    if sort not in {"popular", "a-z"}:
        raise HTTPException(status_code=400, detail="Tag sort must be popular or a-z")
    return {
        "source": "heh",
        "sort": sort,
        "count_scope": "downloaded-library",
        "tags": queries.downloaded_tag_directory(sort),
    }


# ---- Reading history ----

@router.get("/api/manga/history")
def manga_reading_history(limit: int = 60, offset: int = 0) -> dict[str, Any]:
    return queries.reading_history(limit=limit, offset=offset)


@router.get("/api/manga/history/progress/{gallery_id}")
def manga_reading_progress(gallery_id: int) -> dict[str, Any]:
    return {
        "progress": queries.reading_progress(
            gallery_id, source=queries.source_for_gallery_id(gallery_id)
        )
    }


@router.post("/api/manga/history/{gallery_id}")
def save_manga_reading_progress(gallery_id: int, body: ReadingProgressUpdate) -> dict[str, Any]:
    return queries.save_reading_progress(
        gallery_id,
        title=body.title,
        cover_path=body.cover_path,
        last_page=body.page,
        page_count=body.page_count,
        source=queries.source_for_gallery_id(gallery_id),
    )


# ---- Favorites / pins / categories ----

@router.post("/api/manga/favorite/{gallery_id}")
def toggle_manga_favorite(gallery_id: int) -> dict[str, Any]:
    return {
        "favorite": queries.toggle_favorite(
            gallery_id, source=queries.source_for_gallery_id(gallery_id)
        )
    }


@router.post("/api/manga/pin/{gallery_id}")
def toggle_manga_pin(gallery_id: int) -> dict[str, Any]:
    return {
        "pinned": queries.toggle_pinned(
            gallery_id, source=queries.source_for_gallery_id(gallery_id)
        )
    }


class CategoryCreate(BaseModel):
    name: str


@router.get("/api/manga/categories")
def list_manga_categories() -> dict[str, Any]:
    return {"categories": queries.list_categories()}


@router.post("/api/manga/categories")
def create_manga_category(body: CategoryCreate) -> dict[str, Any]:
    result = queries.create_category(body.name)
    if not result.get("ok"):
        raise HTTPException(400, result.get("error", "Could not create category"))
    return {"ok": True, "categories": queries.list_categories()}


@router.delete("/api/manga/categories/{category_id}")
def delete_manga_category(category_id: int) -> dict[str, Any]:
    queries.delete_category(category_id)
    return {"ok": True, "categories": queries.list_categories()}


@router.post("/api/manga/categories/{category_id}/toggle/{gallery_id}")
def toggle_manga_category(category_id: int, gallery_id: int) -> dict[str, Any]:
    return {
        "member": queries.toggle_category_membership(
            gallery_id, category_id, source=queries.source_for_gallery_id(gallery_id)
        )
    }


# ---- Series (ordered multi-chapter works) ----

class SeriesCreate(BaseModel):
    title: str
    gallery_ids: list[int] = []


class SeriesRename(BaseModel):
    title: str


class SeriesAddItem(BaseModel):
    gallery_id: int


class SeriesReorder(BaseModel):
    gallery_ids: list[int]


@router.get("/api/manga/series")
def list_manga_series() -> dict[str, Any]:
    return {"series": queries.list_series()}


@router.post("/api/manga/series")
def create_manga_series(body: SeriesCreate) -> dict[str, Any]:
    source = queries.source_for_gallery_id(body.gallery_ids[0]) if body.gallery_ids else "nhentai"
    result = queries.create_series(body.title, body.gallery_ids, source=source)
    if not result.get("ok"):
        raise HTTPException(400, result.get("error", "Could not create series"))
    return {"ok": True, "series_id": result["series_id"], "series": queries.list_series()}


@router.get("/api/manga/series/{series_id}")
def manga_series_detail(series_id: int) -> dict[str, Any]:
    detail = queries.series_detail(series_id)
    if detail is None:
        raise HTTPException(404, "Series not found")
    return detail


@router.patch("/api/manga/series/{series_id}")
def rename_manga_series(series_id: int, body: SeriesRename) -> dict[str, Any]:
    result = queries.rename_series(series_id, body.title)
    if not result.get("ok"):
        raise HTTPException(400, result.get("error", "Could not rename series"))
    return {"ok": True, "series": queries.list_series()}


@router.delete("/api/manga/series/{series_id}")
def delete_manga_series(series_id: int) -> dict[str, Any]:
    queries.delete_series(series_id)
    return {"ok": True, "series": queries.list_series()}


@router.put("/api/manga/series/{series_id}/order")
def reorder_manga_series(series_id: int, body: SeriesReorder) -> dict[str, Any]:
    source = queries.source_for_gallery_id(body.gallery_ids[0]) if body.gallery_ids else "nhentai"
    queries.reorder_series(series_id, body.gallery_ids, source=source)
    return {"ok": True}


@router.post("/api/manga/series/{series_id}/items")
def add_manga_series_item(series_id: int, body: SeriesAddItem) -> dict[str, Any]:
    result = queries.add_to_series(
        series_id, body.gallery_id, source=queries.source_for_gallery_id(body.gallery_id)
    )
    if not result.get("ok"):
        raise HTTPException(404, result.get("error", "Could not add to series"))
    return {"ok": True, "series": queries.list_series()}


@router.delete("/api/manga/series/items/{gallery_id}")
def remove_manga_series_item(gallery_id: int) -> dict[str, Any]:
    queries.remove_from_series(gallery_id, source=queries.source_for_gallery_id(gallery_id))
    return {"ok": True, "series": queries.list_series()}


@router.post("/api/manga/series/items/{gallery_id}/first")
def set_manga_series_first(gallery_id: int) -> dict[str, Any]:
    result = queries.set_series_first(
        gallery_id, source=queries.source_for_gallery_id(gallery_id)
    )
    if not result.get("ok"):
        raise HTTPException(400, result.get("error", "Could not set chapter"))
    return {"ok": True}


# ---- Browse (online, opt-in) ----

def _nh_guard() -> None:
    try:
        nhentai.require_enabled()
    except nhentai.NhDisabledError as exc:
        raise HTTPException(403, str(exc)) from exc


def _nh_call(function, *args, **kwargs):
    try:
        return function(*args, **kwargs)
    except nhentai.NhError as exc:
        raise HTTPException(exc.status if 400 <= exc.status < 600 else 502, str(exc)) from exc


_browse_cache: dict[str, tuple[float, dict[str, Any]]] = {}
_BROWSE_TTL = 60.0

NH_PATH_RE = re.compile(r"^galleries/[A-Za-z0-9._/-]+$")


def _cached_browse_page(
    query: str,
    upstream_page: int,
    sort: str,
    language: str,
) -> dict[str, Any]:
    cache_key = f"{query}\x1f{upstream_page}\x1f{sort}\x1f{language}"
    cached = _browse_cache.get(cache_key)
    if cached and time.monotonic() - cached[0] < _BROWSE_TTL:
        return cached[1]

    result = _nh_call(nhentai.browse_galleries, query, upstream_page, sort, language)
    _browse_cache[cache_key] = (time.monotonic(), result)
    if len(_browse_cache) > 100:
        oldest = min(_browse_cache, key=lambda key: _browse_cache[key][0])
        _browse_cache.pop(oldest, None)
    return result


@router.get("/api/manga/browse")
def browse_nhentai(
    query: str = "",
    page: int = 1,
    per_page: int = 25,
    sort: str = "recent",
    language: str = "all",
) -> dict[str, Any]:
    _nh_guard()
    manga_settings = get_manga_settings()
    ignored_tags = sorted(
        {tag.strip().lower() for tag in manga_settings["ignored_tags"] if tag.strip()}
    )
    upstream_query = query
    if ignored_tags and not manga_settings["show_ignored"]:
        exclusions = [
            f'-"{tag.replace(chr(34), " ")}"' if " " in tag else f"-{tag}"
            for tag in ignored_tags
        ]
        upstream_query = " ".join([query.strip(), *exclusions]).strip()

    metadata = _cached_browse_page(upstream_query, 1, sort, language)
    upstream_pages = max(1, int(metadata.get("num_pages") or 1))
    last_result = (
        metadata
        if upstream_pages == 1
        else _cached_browse_page(upstream_query, upstream_pages, sort, language)
    )
    total = exact_total(upstream_pages, len(last_result.get("items") or []))
    page_count = logical_page_count(total, per_page)
    page = min(max(1, page), page_count)
    window = browse_window(page, per_page)

    gathered: list[dict[str, Any]] = []
    for upstream_page in range(window.first_upstream_page, window.last_upstream_page + 1):
        if upstream_page > upstream_pages:
            break
        if upstream_page == 1:
            result = metadata
        elif upstream_page == upstream_pages:
            result = last_result
        else:
            result = _cached_browse_page(upstream_query, upstream_page, sort, language)
        gathered.extend(result.get("items") or [])

    items = gathered[window.offset : window.offset + window.per_page]
    gallery_ids = [item["id"] for item in items]
    downloaded = queries.downloaded_gallery_ids(gallery_ids)
    downloaded_elsewhere = queries.imported_downloaded_gallery_ids(gallery_ids)
    tag_ids = [tag_id for item in items for tag_id in (item.get("tag_ids") or [])]
    tag_info = queries.tag_info_by_nh_ids(tag_ids)
    enriched = []
    for item in items:
        known_tags = [
            tag_info[tag_id] for tag_id in (item.get("tag_ids") or []) if tag_id in tag_info
        ]
        ignored_matches = sorted(
            {tag["name"] for tag in known_tags if tag["name"].lower() in ignored_tags},
            key=str.lower,
        )
        enriched.append(
            {
                **item,
                "downloaded": item["id"] in downloaded,
                "downloaded_elsewhere": item["id"] in downloaded_elsewhere,
                "known_tags": known_tags,
                "ignored_matches": ignored_matches,
            }
        )
    return {
        "items": enriched,
        "num_pages": page_count,
        "page": page,
        "per_page": window.per_page,
        "total": total,
        "has_more": window.start + len(items) < total,
    }


@router.get("/api/manga/gallery/{gallery_id}")
def remote_gallery(gallery_id: int) -> dict[str, Any]:
    """Full metadata, preferring an indexed local gallery before any network call."""
    local = queries.get_manga_by_gallery_id(gallery_id)
    if local is not None:
        detail = queries.get_manga_by_id(local["id"])
        try:
            gallery = json.loads((detail or {}).get("raw_json") or "")
            if not isinstance(gallery, dict):
                raise ValueError("raw metadata is not an object")
        except (json.JSONDecodeError, TypeError, ValueError):
            gallery = {"id": gallery_id, "title": {"pretty": local["title"]}, "tags": [], "pages": []}
        gallery["downloaded"] = True
        gallery["local_manga_id"] = local["id"]
        return gallery

    _nh_guard()
    gallery = _nh_call(nhentai.get_gallery, gallery_id)
    gallery["downloaded"] = False
    return gallery


@router.get("/api/manga/nh-image")
def proxy_nh_image(path: str, kind: str = "thumb") -> Response:
    """Server-side image proxy so browse covers dodge CORS/hotlink protection.
    Only nHentai gallery CDN paths are allowed — this is not an open proxy."""
    _nh_guard()
    if not NH_PATH_RE.match(path or ""):
        raise HTTPException(400, "Invalid image path")
    if kind not in ("thumb", "image"):
        raise HTTPException(400, "Invalid kind")
    data, content_type = _nh_call(nhentai.fetch_image_by_path, path, kind)
    return Response(
        content=data,
        media_type=content_type,
        headers={"Cache-Control": "public, max-age=3600"},
    )


# ---- MangaDex Browse (public API, explicit source selection) ----


def _md_call(function, *args, **kwargs):
    try:
        return function(*args, **kwargs)
    except mangadex.MangaDexError as exc:
        raise HTTPException(exc.status if 400 <= exc.status < 600 else 502, str(exc)) from exc


def _csv_values(value: str) -> list[str]:
    return list(
        dict.fromkeys(item.strip() for item in (value or "").split(",") if item.strip())
    )


@router.get("/api/manga/remote/mangadex/browse")
def browse_mangadex(
    query: str = "",
    page: int = 1,
    per_page: int = 20,
    sort: str = "latest",
    language: str = "all",
    original_languages: str = "",
    content_ratings: str = "",
    publication_demographics: str = "",
    statuses: str = "",
    included_tags: str = "",
    tags_mode: str = "AND",
) -> dict[str, Any]:
    manga_settings = get_manga_settings()
    ignored_tags = sorted(
        {tag.strip().lower() for tag in manga_settings["ignored_tags"] if tag.strip()}
    )
    excluded = ignored_tags if not manga_settings["show_ignored"] else []
    result = _md_call(
        mangadex.search_titles,
        query,
        page=page,
        per_page=per_page,
        sort=sort,
        language=language,
        original_languages=_csv_values(original_languages),
        content_ratings=_csv_values(content_ratings),
        publication_demographics=_csv_values(publication_demographics),
        statuses=_csv_values(statuses),
        included_tag_ids=_csv_values(included_tags),
        tags_mode=tags_mode,
        excluded_tag_names=excluded,
    )
    parent_counts = queries.downloaded_parent_counts(
        [str(item["id"]) for item in result["items"]], "mangadex"
    )
    for item in result["items"]:
        item["downloaded_chapters"] = parent_counts.get(str(item["id"]), 0)
        item["ignored_matches"] = sorted(
            {
                str(tag["name"])
                for tag in item.get("tags") or []
                if str(tag.get("name") or "").lower() in ignored_tags
            },
            key=str.casefold,
        )
    return result


@router.get("/api/manga/remote/mangadex/filters")
def mangadex_filters() -> dict[str, Any]:
    return _md_call(mangadex.filter_catalog)


@router.get("/api/manga/remote/mangadex/title/{title_id}")
def mangadex_title(title_id: str) -> dict[str, Any]:
    title = _md_call(mangadex.get_title, title_id)
    title["downloaded_chapters"] = queries.downloaded_parent_counts(
        [title["id"]], "mangadex"
    ).get(title["id"], 0)
    return title


@router.get("/api/manga/remote/mangadex/title/{title_id}/chapters")
def mangadex_chapters(
    title_id: str,
    language: str = "all",
    limit: int = 500,
    offset: int = 0,
) -> dict[str, Any]:
    result = _md_call(
        mangadex.list_chapters,
        title_id,
        language=language,
        limit=limit,
        offset=offset,
    )
    downloaded = queries.downloaded_external_ids(
        [str(item["id"]) for item in result["items"]], "mangadex"
    )
    for item in result["items"]:
        item["downloaded"] = item["id"] in downloaded
    return result


@router.get("/api/manga/remote/mangadex/chapter/{chapter_id}")
def mangadex_chapter_context(chapter_id: str) -> dict[str, Any]:
    chapter = _md_call(mangadex.get_chapter, chapter_id)
    title = _md_call(mangadex.get_title, chapter["manga_id"])
    local = queries.get_manga_by_external_id(chapter["id"], "mangadex")
    return {"chapter": chapter, "title": title, "local": local}


@router.get("/api/manga/remote/mangadex/chapter/{chapter_id}/pages")
def mangadex_page_list(chapter_id: str) -> dict[str, Any]:
    chapter = _md_call(mangadex.get_chapter, chapter_id)
    if chapter.get("external_url"):
        return {
            "chapter_id": chapter["id"],
            "pages": 0,
            "data_saver": 0,
            "external_url": chapter["external_url"],
        }
    return _md_call(mangadex.chapter_pages, chapter["id"])


@router.get("/api/manga/remote/mangadex/chapter/{chapter_id}/page/{number}")
def proxy_mangadex_page(chapter_id: str, number: int, quality: str = "data-saver") -> Response:
    data, content_type, _name = _md_call(
        mangadex.fetch_chapter_page, chapter_id, number, quality
    )
    return Response(
        content=data,
        media_type=content_type,
        headers={"Cache-Control": "private, max-age=900"},
    )


@router.get("/api/manga/remote/mangadex/cover/{title_id}/{filename}")
def proxy_mangadex_cover(title_id: str, filename: str, size: int = 512) -> Response:
    data, content_type = _md_call(mangadex.fetch_cover, title_id, filename, size)
    return Response(
        content=data,
        media_type=content_type,
        headers={"Cache-Control": "public, max-age=86400"},
    )


@router.get("/api/manga/remote/mangadex/chapter/{chapter_id}/progress")
def mangadex_reading_progress(chapter_id: str) -> dict[str, Any]:
    chapter_id = _md_call(mangadex.validate_uuid, chapter_id, "MangaDex chapter ID")
    gallery_id = remote_gallery_id("mangadex", chapter_id, create=False)
    return {
        "gallery_id": gallery_id,
        "progress": queries.reading_progress(gallery_id, source="mangadex")
        if gallery_id is not None
        else None,
    }


@router.post("/api/manga/remote/mangadex/chapter/{chapter_id}/progress")
def save_mangadex_reading_progress(
    chapter_id: str, body: ReadingProgressUpdate
) -> dict[str, Any]:
    chapter_id = _md_call(mangadex.validate_uuid, chapter_id, "MangaDex chapter ID")
    gallery_id = remote_gallery_id("mangadex", chapter_id, create=True)
    if gallery_id is None:
        raise HTTPException(500, "Could not allocate MangaDex reading identity")
    return queries.save_reading_progress(
        gallery_id,
        title=body.title,
        cover_path=body.cover_path,
        last_page=body.page,
        page_count=body.page_count,
        source="mangadex",
    )


@router.post("/api/manga/remote/mangadex/download/{chapter_id}")
def queue_mangadex_download(chapter_id: str) -> dict[str, Any]:
    return _md_call(downloader.enqueue_mangadex_download, chapter_id)


# ---- Downloads (online, opt-in) ----

@router.post("/api/manga/download/{gallery_id}")
def queue_download(gallery_id: int) -> dict[str, Any]:
    _nh_guard()
    return _nh_call(downloader.enqueue_download, gallery_id)


@router.get("/api/manga/downloads")
def download_queue_state() -> dict[str, Any]:
    return downloader.download_state()


@router.get("/api/manga/downloads/recent")
def recent_downloaded_manga(limit: int = 6, offset: int = 0) -> dict[str, Any]:
    manga_settings = get_manga_settings()
    return queries.recent_downloads(
        limit=limit,
        offset=offset,
        ignored_tags=manga_settings["ignored_tags"],
        show_ignored=manga_settings["show_ignored"],
    )


# ---- Maintenance jobs ----

@router.post("/api/manga/enrich")
def start_manga_enrich() -> dict[str, Any]:
    _nh_guard()
    started = _nh_call(jobs.start_enrich)
    if not started:
        raise HTTPException(409, "Enrich is already running")
    return {"ok": True}


@router.get("/api/manga/enrich")
def manga_enrich_progress() -> dict[str, Any]:
    progress = jobs.enrich_progress()
    progress["unmatched"] = jobs.unmatched_count()
    return progress


class MigrateRequest(BaseModel):
    root_id: int


@router.post("/api/manga/migrate")
def start_manga_migrate(body: MigrateRequest) -> dict[str, Any]:
    if manga_roots.get_root(body.root_id) is None:
        raise HTTPException(404, "Root not found")
    started = jobs.start_migrate(body.root_id)
    if not started:
        raise HTTPException(409, "Convert is already running")
    return {"ok": True}


@router.get("/api/manga/migrate")
def manga_migrate_progress() -> dict[str, Any]:
    return jobs.migrate_progress()
