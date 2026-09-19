"""Provider-aware download queue for nHentai galleries and MangaDex chapters.

Requires online nHentai access to be enabled. Pages are fetched a few at a
time; a single failure aborts that gallery and is remembered in the recents.
"""
from __future__ import annotations

import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from manga import mangadex
from manga.cbz import build_cbz, build_cbz_stream
from manga.covers import generate_cover
from manga.database import remote_gallery_id
from manga.manatan import chapter_paths_for, mangadex_chapter_paths_for, page_name, write_manifest
from manga.metadata import file_size_of, upsert_manga, write_sidecar
from manga.nhentai import (
    NhError,
    best_title,
    ext_from_path,
    fetch_image_by_path,
    get_gallery,
    require_enabled,
)
from manga.queries import get_manga_by_external_id, get_manga_by_gallery_id
from manga.roots import download_root

logger = logging.getLogger("keivotos")

PAGE_CONCURRENCY = 4
RECENT_LIMIT = 20

_lock = threading.Lock()
_queue: list[dict[str, Any]] = []
_current: dict[str, Any] | None = None
_recent: list[dict[str, Any]] = []
_processing = False


def download_state() -> dict[str, Any]:
    with _lock:
        return {
            "running": _processing,
            "current": dict(_current) if _current else None,
            "queue": [dict(item) for item in _queue],
            "recent": [dict(item) for item in _recent[:8]],
        }


def enqueue_download(gallery_id: int) -> dict[str, Any]:
    """Queue a gallery. Returns {queued: bool, reason?: str}."""
    require_enabled()
    if get_manga_by_gallery_id(gallery_id) is not None:
        return {"queued": False, "reason": "Already downloaded"}
    with _lock:
        if _current is not None and _current["gallery_id"] == gallery_id:
            return {"queued": False, "reason": "Already downloading"}
        if any(item["gallery_id"] == gallery_id for item in _queue):
            return {"queued": False, "reason": "Already queued"}
        _queue.append(
            {
                "source": "nhentai",
                "gallery_id": gallery_id,
                "external_id": str(gallery_id),
                "title": f"#{gallery_id}",
                "status": "queued",
                "page": 0,
                "pages": 0,
            }
        )
    _start_worker()
    return {"queued": True}


def enqueue_mangadex_download(chapter_id: str) -> dict[str, Any]:
    """Queue one MangaDex chapter without fetching any page bytes yet."""
    chapter_id = mangadex.validate_uuid(chapter_id, "MangaDex chapter ID")
    if get_manga_by_external_id(chapter_id, "mangadex") is not None:
        return {"queued": False, "reason": "Already downloaded"}
    with _lock:
        if (
            _current is not None
            and _current.get("source") == "mangadex"
            and _current.get("external_id") == chapter_id
        ):
            return {"queued": False, "reason": "Already downloading"}
        if any(
            item.get("source") == "mangadex" and item.get("external_id") == chapter_id
            for item in _queue
        ):
            return {"queued": False, "reason": "Already queued"}
        _queue.append(
            {
                "source": "mangadex",
                "gallery_id": None,
                "external_id": chapter_id,
                "title": "MangaDex chapter",
                "status": "queued",
                "page": 0,
                "pages": 0,
            }
        )
    _start_worker()
    return {"queued": True}


def _start_worker() -> None:
    global _processing
    with _lock:
        if _processing:
            return
        _processing = True
    threading.Thread(target=_process_queue, name="manayomi-download", daemon=True).start()


def _process_queue() -> None:
    global _current, _processing
    try:
        while True:
            with _lock:
                if not _queue:
                    return
                _current = _queue.pop(0)
                _current["status"] = "downloading"
            item = _current
            try:
                _download_one(item)
                item["status"] = "done"
            except Exception as exc:  # noqa: BLE001 - remembered per item
                item["status"] = "error"
                item["error"] = str(exc)
                logger.error(
                    "manga download failed for %s:%s: %s",
                    item.get("source", "nhentai"),
                    item.get("external_id") or item.get("gallery_id"),
                    exc,
                )
            with _lock:
                _recent.insert(0, dict(item))
                del _recent[RECENT_LIMIT:]
    finally:
        with _lock:
            _current = None
            _processing = False
        try:
            from manga.backup import maybe_backup

            maybe_backup("after-download")
        except Exception:  # noqa: BLE001
            pass


def _download_one(item: dict[str, Any]) -> None:
    if item.get("source") == "mangadex":
        _download_mangadex(item)
        return

    root = download_root()
    if root is None:
        raise NhError("No library folder configured to download into.", 400)

    gallery = get_gallery(item["gallery_id"])
    item["title"] = best_title(gallery)
    item["pages"] = gallery.get("num_pages", 0)

    paths = chapter_paths_for(root["path"], gallery)
    paths["chapter_dir"].mkdir(parents=True, exist_ok=True)

    pages = sorted(gallery.get("pages") or [], key=lambda page: page.get("number", 0))
    if not pages:
        raise NhError("Gallery has no pages.", 404)

    entries: list[tuple[str, bytes] | None] = [None] * len(pages)
    progress_lock = threading.Lock()

    def fetch_page(index: int) -> None:
        data, _content_type = fetch_image_by_path(pages[index]["path"], "image")
        entries[index] = (page_name(index, ext_from_path(pages[index]["path"])), data)
        with progress_lock:
            item["page"] += 1

    with ThreadPoolExecutor(max_workers=min(PAGE_CONCURRENCY, len(pages))) as pool:
        for future in [pool.submit(fetch_page, index) for index in range(len(pages))]:
            future.result()  # re-raises the first failure

    complete = [entry for entry in entries if entry is not None]
    build_cbz(paths["cbz_path"], complete)
    write_manifest(paths["chapter_dir"], [name for name, _ in complete])
    write_sidecar(paths["cbz_path"], gallery)

    # Cover: prefer nHentai's dedicated cover image, fall back to the first page.
    cover_name: str | None = None
    try:
        cover_data, _ = fetch_image_by_path(gallery["cover"]["path"], "thumb")
        cover_name = generate_cover(item["gallery_id"], cover_data)
    except Exception:  # noqa: BLE001
        cover_name = generate_cover(item["gallery_id"], complete[0][1])

    upsert_manga(
        gallery_id=item["gallery_id"],
        file_path=paths["cbz_path"],
        root_id=root["id"],
        cover_name=cover_name,
        file_size=file_size_of(paths["cbz_path"]),
        gallery=gallery,
    )


def _download_mangadex(item: dict[str, Any]) -> None:
    root = download_root()
    if root is None:
        raise mangadex.MangaDexError("No library folder configured to download into.", 400)

    chapter_id = mangadex.validate_uuid(str(item["external_id"]), "MangaDex chapter ID")
    chapter = mangadex.get_chapter(chapter_id)
    if chapter.get("external_url"):
        raise mangadex.MangaDexError(
            "This chapter is hosted by its publisher and cannot be downloaded from MangaDex.",
            409,
        )
    manga_id = str(chapter.get("manga_id") or "")
    if not manga_id:
        raise mangadex.MangaDexError("MangaDex chapter has no parent title.", 502)
    title = mangadex.get_title(manga_id)
    local_id = remote_gallery_id("mangadex", chapter_id, create=True)
    if local_id is None:
        raise mangadex.MangaDexError("Could not allocate a local chapter identity.", 500)

    gallery = mangadex.library_gallery(title, chapter, local_id)
    item["gallery_id"] = local_id
    item["title"] = gallery["title"]["pretty"]
    page_info = mangadex.chapter_pages(chapter_id)
    item["pages"] = int(page_info["pages"])
    chapter["pages"] = item["pages"]
    if item["pages"] <= 0:
        raise mangadex.MangaDexError("MangaDex chapter has no hosted pages.", 404)

    paths = mangadex_chapter_paths_for(root["path"], title, chapter)
    if paths["cbz_path"].exists():
        raise mangadex.MangaDexError(
            "This chapter archive already exists. Scan the library to index it.",
            409,
        )
    paths["chapter_dir"].mkdir(parents=True, exist_ok=True)
    written_names: list[str] = []
    first_page: list[bytes] = []

    def pages():
        for index in range(item["pages"]):
            data, _content_type, provider_name = mangadex.fetch_chapter_page(
                chapter_id, index, "data"
            )
            extension = provider_name.rsplit(".", 1)[-1].lower() if "." in provider_name else "jpg"
            name = page_name(index, extension)
            written_names.append(name)
            if index == 0:
                first_page.append(data)
            item["page"] = index + 1
            yield name, data

    build_cbz_stream(paths["cbz_path"], pages())
    write_manifest(paths["chapter_dir"], written_names)
    mangadex.write_download_sidecar(paths["cbz_path"], title, chapter)

    cover_name: str | None = None
    if title.get("cover_filename"):
        try:
            cover_data, _ = mangadex.fetch_cover(
                title["id"], str(title["cover_filename"]), size=0
            )
            cover_name = generate_cover(local_id, cover_data)
        except Exception:  # noqa: BLE001 - first page is a safe local fallback
            cover_name = None
    if cover_name is None and first_page:
        cover_name = generate_cover(local_id, first_page[0])

    local_manga_id = upsert_manga(
        gallery_id=local_id,
        external_id=chapter_id,
        parent_external_id=title["id"],
        source="mangadex",
        file_path=paths["cbz_path"],
        root_id=root["id"],
        cover_name=cover_name,
        file_size=file_size_of(paths["cbz_path"]),
        gallery=gallery,
    )
    item["local_manga_id"] = local_manga_id
