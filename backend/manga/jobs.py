"""Background maintenance jobs: enrich (retry metadata) and convert
(flat <id>.cbz → nested Manatan tree). Ports of enrich.ts / migrate.ts.
One job of each kind at a time; progress is polled by the UI.
"""
from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import Any

from manga.backup import maybe_backup
from manga.covers import generate_cover_from_cbz
from manga.database import index_session
from manga.manatan import ARCHIVE_FILE, chapter_paths_for, write_manifest
from manga.metadata import file_size_of, read_sidecar, upsert_manga, write_sidecar
from manga.nhentai import NhError, get_gallery, require_enabled
from manga.roots import get_root, mark_scanned

logger = logging.getLogger("keivotos")

_enrich_lock = threading.Lock()
_migrate_lock = threading.Lock()


def _idle(extra: dict[str, Any] | None = None) -> dict[str, Any]:
    base: dict[str, Any] = {
        "running": False,
        "total": 0,
        "processed": 0,
        "errors": 0,
        "current": "",
        "started_at": 0,
        "finished_at": None,
        "message": "idle",
    }
    if extra:
        base.update(extra)
    return base


_enrich_progress = _idle({"enriched": 0, "still_missing": 0})
_migrate_progress = _idle({"root_id": None, "moved": 0, "skipped": 0})


def enrich_progress() -> dict[str, Any]:
    return dict(_enrich_progress)


def migrate_progress() -> dict[str, Any]:
    return dict(_migrate_progress)


def unmatched_count() -> int:
    with index_session() as index:
        return index.execute("SELECT COUNT(*) FROM manga WHERE matched = 0").fetchone()[0]


def start_enrich() -> bool:
    """Fetch metadata for every unmatched manga. Requires online access."""
    global _enrich_progress
    require_enabled()
    with _enrich_lock:
        if _enrich_progress["running"]:
            return False
        _enrich_progress = _idle({"enriched": 0, "still_missing": 0})
        _enrich_progress.update(
            {"running": True, "started_at": int(time.time() * 1000), "message": "enriching…"}
        )
    threading.Thread(target=_run_enrich, name="manayomi-enrich", daemon=True).start()
    return True


def _run_enrich() -> None:
    progress = _enrich_progress
    try:
        with index_session() as index:
            rows = [
                dict(row)
                for row in index.execute(
                    "SELECT id, gallery_id, file_path, root_id FROM manga WHERE matched = 0"
                )
            ]
        progress["total"] = len(rows)
        for row in rows:
            progress["current"] = f"#{row['gallery_id']}"
            try:
                gallery = get_gallery(row["gallery_id"])
                write_sidecar(row["file_path"], gallery)
                cover_name = generate_cover_from_cbz(row["gallery_id"], row["file_path"])
                upsert_manga(
                    gallery_id=row["gallery_id"],
                    file_path=row["file_path"],
                    root_id=row["root_id"],
                    cover_name=cover_name,
                    file_size=file_size_of(row["file_path"]),
                    gallery=gallery,
                )
                progress["enriched"] += 1
            except NhError as exc:
                progress["still_missing"] += 1
                if exc.status in (403, 429, 503):
                    progress["message"] = f"stopped: {exc}"
                    return  # blocked/limited — pointless to hammer on
            except Exception as exc:  # noqa: BLE001
                progress["errors"] += 1
                logger.error("manga enrich error on %s: %s", row["gallery_id"], exc)
            finally:
                progress["processed"] += 1
        progress["message"] = (
            f"done — {progress['enriched']} enriched, {progress['still_missing']} still missing"
        )
    except Exception as exc:  # noqa: BLE001
        progress["message"] = f"enrich failed: {exc}"
        logger.error("manga enrich failed: %s", exc)
    finally:
        progress["running"] = False
        progress["finished_at"] = int(time.time() * 1000)
        progress["current"] = ""
        try:
            maybe_backup("after-enrich")
        except Exception:  # noqa: BLE001
            pass


def start_migrate(root_id: int) -> bool:
    """Convert flat ``<id>.cbz`` files under a root into the nested Manatan tree.
    Moves files (explicit user action); metadata comes from the sidecar or,
    when online access is enabled, from nHentai."""
    global _migrate_progress
    with _migrate_lock:
        if _migrate_progress["running"]:
            return False
        root = get_root(root_id)
        if root is None:
            return False
        _migrate_progress = _idle({"root_id": root_id, "moved": 0, "skipped": 0})
        _migrate_progress.update(
            {"running": True, "started_at": int(time.time() * 1000), "message": "listing flat files…"}
        )
    threading.Thread(
        target=_run_migrate, args=(root,), name="manayomi-migrate", daemon=True
    ).start()
    return True


def _walk_flat(directory: Path, out: list[Path]) -> list[Path]:
    """Flat numeric ``<id>.cbz`` files; nested chapter trees are already done."""
    try:
        entries = sorted(directory.iterdir(), key=lambda item: item.name.casefold())
    except OSError:
        return out
    for entry in entries:
        if entry.is_dir():
            _walk_flat(entry, out)
        elif entry.is_file() and entry.suffix.lower() == ".cbz" and entry.stem.isdigit():
            out.append(entry)
    return out


def _run_migrate(root: dict[str, Any]) -> None:
    from manga.settings import nhentai_enabled

    progress = _migrate_progress
    try:
        files = _walk_flat(Path(root["path"]), [])
        progress["total"] = len(files)
        progress["message"] = "converting…"
        online = nhentai_enabled()

        for file_path in files:
            progress["current"] = file_path.name
            try:
                gallery_id = int(file_path.stem)
                gallery = read_sidecar(file_path)
                if gallery is None and online:
                    try:
                        gallery = get_gallery(gallery_id)
                    except NhError:
                        gallery = None
                if gallery is None:
                    # No metadata → no title for the folder name; leave it flat.
                    progress["skipped"] += 1
                    continue

                paths = chapter_paths_for(root["path"], gallery)
                target = paths["cbz_path"]
                if target.exists():
                    progress["skipped"] += 1
                    continue
                paths["chapter_dir"].mkdir(parents=True, exist_ok=True)
                file_path.replace(target)
                old_sidecar = file_path.with_suffix(".json")
                if old_sidecar.is_file():
                    old_sidecar.replace(paths["chapter_dir"] / "nhentai.json")
                else:
                    write_sidecar(target, gallery)
                from manga.cbz import list_images

                write_manifest(paths["chapter_dir"], list_images(target))
                cover_name = generate_cover_from_cbz(gallery_id, target)
                upsert_manga(
                    gallery_id=gallery_id,
                    file_path=target,
                    root_id=root["id"],
                    cover_name=cover_name,
                    file_size=file_size_of(target),
                    gallery=gallery,
                )
                progress["moved"] += 1
            except Exception as exc:  # noqa: BLE001
                progress["errors"] += 1
                logger.error("manga convert error on %s: %s", file_path, exc)
            finally:
                progress["processed"] += 1

        mark_scanned(root["id"])
        progress["message"] = (
            f"done — {progress['moved']} converted, {progress['skipped']} skipped"
        )
    except Exception as exc:  # noqa: BLE001
        progress["message"] = f"convert failed: {exc}"
        logger.error("manga convert failed: %s", exc)
    finally:
        progress["running"] = False
        progress["finished_at"] = int(time.time() * 1000)
        progress["current"] = ""
        try:
            maybe_backup("after-convert")
        except Exception:  # noqa: BLE001
            pass
