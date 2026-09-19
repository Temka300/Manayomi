"""Library scan (port of scanner.ts): register every .cbz under a root.

Idempotent — files already indexed (by path) are skipped instantly. Reads the
sidecar when present; optionally fetches metadata from nHentai (writing the
sidecar) when online access is enabled. Network misses still register the file
untagged so a later scan/enrich can finish the job. One scan at a time.
"""
from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import Any

from manga.covers import generate_cover_from_cbz
from manga import mangadex
from manga.database import index_session, remote_gallery_id
from manga.manatan import id_from_segment
from manga.metadata import file_size_of, read_sidecar, upsert_manga, write_sidecar
from manga.nhentai import NhError, get_gallery
from manga.roots import get_root, mark_scanned
from manga.settings import nhentai_enabled

logger = logging.getLogger("keivotos")

_lock = threading.Lock()


def _idle() -> dict[str, Any]:
    return {
        "running": False,
        "root_id": None,
        "total": 0,
        "processed": 0,
        "added": 0,
        "matched": 0,
        "skipped": 0,
        "errors": 0,
        "current_file": "",
        "started_at": 0,
        "finished_at": None,
        "message": "idle",
    }


_progress: dict[str, Any] = _idle()


def scan_progress() -> dict[str, Any]:
    return dict(_progress)


def _walk_cbz(directory: Path, out: list[Path]) -> list[Path]:
    """Recursively collect every .cbz (flat <id>.cbz and nested chapter.cbz)."""
    try:
        entries = sorted(directory.iterdir(), key=lambda item: item.name.casefold())
    except OSError:
        return out
    for entry in entries:
        if entry.is_dir():
            _walk_cbz(entry, out)
        elif entry.is_file() and entry.suffix.lower() == ".cbz":
            out.append(entry)
    return out


def gallery_id_from_path(file_path: Path) -> int | None:
    """Gallery id from the path alone: flat ``<id>.cbz`` or ``--m<id>``/``--c<id>``
    suffixes on the chapter/manga folders of a nested ``chapter.cbz``."""
    if file_path.name.lower() == "chapter.cbz":
        return (
            id_from_segment(file_path.parent.parent.name)
            or id_from_segment(file_path.parent.name)
        )
    stem = file_path.stem
    return int(stem) if stem.isdigit() else None


def start_scan(root_id: int, enrich: bool = True) -> bool:
    """Begin a scan in a background thread. Returns False if one is running."""
    global _progress
    with _lock:
        if _progress["running"]:
            return False
        root = get_root(root_id)
        if root is None:
            return False
        _progress = {
            **_idle(),
            "running": True,
            "root_id": root_id,
            "started_at": int(time.time() * 1000),
            "message": "listing files…",
        }
    thread = threading.Thread(
        target=_run_scan, args=(root, enrich), name="manayomi-scan", daemon=True
    )
    thread.start()
    return True


def _run_scan(root: dict[str, Any], enrich: bool) -> None:
    global _progress
    try:
        files = _walk_cbz(Path(root["path"]), [])
        _progress["total"] = len(files)
        _progress["message"] = "scanning…"
        online = enrich and nhentai_enabled()

        # One connection for the fast "already indexed?" checks.
        with index_session() as index:
            known_paths = {row[0] for row in index.execute("SELECT file_path FROM manga")}

        for file_path in files:
            _progress["current_file"] = file_path.name
            try:
                if str(file_path) in known_paths:
                    _progress["skipped"] += 1
                    continue

                mangadex_sidecar = mangadex.read_download_sidecar(file_path)
                if mangadex_sidecar is not None:
                    title = mangadex_sidecar["title"]
                    chapter = mangadex_sidecar["chapter"]
                    external_id = str(chapter["id"])
                    local_id = remote_gallery_id("mangadex", external_id, create=True)
                    if local_id is None:
                        raise ValueError("could not allocate MangaDex local identity")
                    gallery = mangadex.library_gallery(title, chapter, local_id)
                    cover_name = generate_cover_from_cbz(local_id, file_path)
                    upsert_manga(
                        gallery_id=local_id,
                        external_id=external_id,
                        parent_external_id=str(title["id"]),
                        source="mangadex",
                        file_path=file_path,
                        root_id=root["id"],
                        cover_name=cover_name,
                        file_size=file_size_of(file_path),
                        gallery=gallery,
                    )
                    _progress["added"] += 1
                    _progress["matched"] += 1
                    continue

                gallery = read_sidecar(file_path)
                gallery_id = (gallery or {}).get("id") or gallery_id_from_path(file_path)
                if gallery_id is None:
                    # Can't map this .cbz to a gallery — leave it alone.
                    _progress["skipped"] += 1
                    continue

                if gallery is None and online:
                    try:
                        gallery = get_gallery(gallery_id)
                        write_sidecar(file_path, gallery)
                    except NhError:
                        pass  # register untagged; a later scan/enrich can retry

                cover_name = generate_cover_from_cbz(gallery_id, file_path)
                upsert_manga(
                    gallery_id=int(gallery_id),
                    file_path=file_path,
                    root_id=root["id"],
                    cover_name=cover_name,
                    file_size=file_size_of(file_path),
                    gallery=gallery,
                )
                _progress["added"] += 1
                if gallery is not None:
                    _progress["matched"] += 1
            except Exception as exc:  # noqa: BLE001 - one bad file must not stop the scan
                _progress["errors"] += 1
                logger.error("manga scan error on %s: %s", file_path, exc)
            finally:
                _progress["processed"] += 1

        mark_scanned(root["id"])
        _progress["message"] = (
            f"done — {_progress['added']} added, {_progress['matched']} matched,"
            f" {_progress['skipped']} skipped"
        )
    except Exception as exc:  # noqa: BLE001
        _progress["message"] = f"scan failed: {exc}"
        logger.error("manga scan failed: %s", exc)
    finally:
        _progress["running"] = False
        _progress["finished_at"] = int(time.time() * 1000)
        _progress["current_file"] = ""
        try:
            from manga.backup import maybe_backup

            maybe_backup("after-scan")
        except Exception:  # noqa: BLE001 - backup failure must not mark the scan failed
            pass
