"""Sidecar files + index-DB upserts for manga (port of metadata.ts).

Sidecar placement follows the file's layout:
- nested ``…/chapter.cbz``  → ``nhentai.json`` beside it in the chapter folder;
- flat ``<id>.cbz``          → ``<id>.json`` next to the archive.
"""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

from manga.database import index_session, user_session
from manga.manatan import ARCHIVE_FILE, NHENTAI_META_FILE
from manga.nhentai import best_title, ext_from_path

logger = logging.getLogger("keivotos")


def sidecar_path_for(cbz_path: str | Path) -> Path:
    path = Path(cbz_path)
    if path.name.lower() == ARCHIVE_FILE:
        return path.parent / NHENTAI_META_FILE
    return path.with_suffix(".json")


def read_sidecar(cbz_path: str | Path) -> dict[str, Any] | None:
    sidecar = sidecar_path_for(cbz_path)
    if not sidecar.is_file():
        return None
    try:
        value = json.loads(sidecar.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("manga sidecar unreadable %s: %s", sidecar, exc)
        return None
    if not isinstance(value, dict) or not isinstance(value.get("id"), int):
        return None
    return value


def write_sidecar(cbz_path: str | Path, gallery: dict[str, Any]) -> None:
    sidecar = sidecar_path_for(cbz_path)
    sidecar.parent.mkdir(parents=True, exist_ok=True)
    temporary = sidecar.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(gallery, indent=2, ensure_ascii=False), encoding="utf-8")
    temporary.replace(sidecar)


def file_size_of(path: str | Path) -> int | None:
    try:
        return Path(path).stat().st_size
    except OSError:
        return None


def _cover_ext(gallery: dict[str, Any]) -> str | None:
    cover = gallery.get("cover") or {}
    path = cover.get("path")
    return ext_from_path(path) if isinstance(path, str) else None


def upsert_manga(
    *,
    gallery_id: int,
    file_path: str | Path,
    root_id: int | None,
    cover_name: str | None,
    file_size: int | None,
    gallery: dict[str, Any] | None,
    source: str = "nhentai",
    external_id: str | None = None,
    parent_external_id: str | None = None,
) -> int:
    """Insert or update one manga row (and its tag links). Returns the row id."""
    now = int(time.time() * 1000)
    file_path = str(file_path)

    if gallery is not None:
        title = gallery.get("title") or {}
        fields = {
            "media_id": gallery.get("media_id"),
            "title": best_title(gallery),
            "title_english": title.get("english"),
            "title_japanese": title.get("japanese"),
            "title_pretty": title.get("pretty"),
            "pages": gallery.get("num_pages"),
            "cover_ext": _cover_ext(gallery),
            "favorites": gallery.get("num_favorites"),
            "scanlator": gallery.get("scanlator") or None,
            "upload_date": (
                int(gallery["upload_date"]) * 1000
                if isinstance(gallery.get("upload_date"), (int, float))
                else None
            ),
            "raw_json": json.dumps(gallery, ensure_ascii=False),
            "matched": 1,
        }
    else:
        fields = {"title": f"#{gallery_id}", "matched": 0}

    with index_session() as index:
        row = index.execute(
            "SELECT id, created_at FROM manga WHERE source = ? AND gallery_id = ?", (source, gallery_id)
        ).fetchone()
        if row is None:
            manga_id = index.execute(
                "INSERT INTO manga (source, gallery_id, root_id, file_path, title, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (source, gallery_id, root_id, file_path, fields.get("title", f"#{gallery_id}"), now),
            ).lastrowid
            added_at = now
        else:
            manga_id = row["id"]
            added_at = int(row["created_at"])
        assignments = {
            "root_id": root_id,
            "file_path": file_path,
            "cover_name": cover_name,
            "file_size": file_size,
            "external_id": external_id,
            "parent_external_id": parent_external_id,
        }
        assignments.update(fields)
        columns = ", ".join(f"{key} = ?" for key in assignments)
        index.execute(
            f"UPDATE manga SET {columns} WHERE id = ?",
            (*assignments.values(), manga_id),
        )

        if gallery is not None:
            _relink_tags(index, int(manga_id), gallery)
    with user_session() as user:
        user.execute(
            "INSERT OR IGNORE INTO library_additions (source, gallery_id, added_at) VALUES (?, ?, ?)",
            (source, gallery_id, added_at),
        )
    return int(manga_id)


def _relink_tags(index, manga_id: int, gallery: dict[str, Any]) -> None:
    old_tag_ids = [row[0] for row in index.execute(
        "SELECT tag_id FROM manga_tags WHERE manga_id = ?", (manga_id,)
    )]
    index.execute("DELETE FROM manga_tags WHERE manga_id = ?", (manga_id,))
    for tag_id in old_tag_ids:
        index.execute("UPDATE tags SET manga_count = manga_count - 1 WHERE id = ?", (tag_id,))

    for tag in gallery.get("tags") or []:
        name = tag.get("name")
        if not isinstance(name, str) or not name.strip():
            continue
        category = tag.get("type") if isinstance(tag.get("type"), str) else "tag"
        nh_id = tag.get("id") if isinstance(tag.get("id"), int) else None
        row = index.execute(
            "SELECT id FROM tags WHERE name = ? AND category = ?", (name, category)
        ).fetchone()
        if row is None:
            tag_id = index.execute(
                "INSERT INTO tags (name, category, nh_id) VALUES (?, ?, ?)",
                (name, category, nh_id),
            ).lastrowid
        else:
            tag_id = row[0]
            if nh_id is not None:
                index.execute("UPDATE tags SET nh_id = COALESCE(nh_id, ?) WHERE id = ?", (nh_id, tag_id))
        inserted = index.execute(
            "INSERT OR IGNORE INTO manga_tags (manga_id, tag_id) VALUES (?, ?)",
            (manga_id, tag_id),
        ).rowcount
        if inserted:
            index.execute("UPDATE tags SET manga_count = manga_count + 1 WHERE id = ?", (tag_id,))

    index.execute("DELETE FROM tags WHERE manga_count <= 0")
