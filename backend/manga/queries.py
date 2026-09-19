"""Library queries (port of queries.ts). Cross-DB reads ATTACH the user DB so
favorites/pins/categories — keyed by (source, gallery_id) — survive index
rebuilds, per the Keivotos two-database contract."""
from __future__ import annotations

import sqlite3
import time
from contextlib import contextmanager
from typing import Any, Iterator

from manga.database import index_db, user_session
from manga.paths import MANGA_USER_DB_PATH
from manga.search import LibraryQuery

TAG_SEP = "\x1f"  # packs tag names into one column; cannot appear in a tag name

ADDED_AT_SQL = """COALESCE(
    (SELECT addition.added_at FROM userdb.library_additions addition
     WHERE addition.source = manga.source AND addition.gallery_id = manga.gallery_id),
    manga.created_at
)"""

LIBRARY_SORTS = {
    "recent": f"{ADDED_AT_SQL} DESC",
    "uploaded": "(manga.upload_date IS NULL) ASC, manga.upload_date DESC, manga.gallery_id DESC",
    "gallery": "manga.gallery_id DESC",
    "title": "manga.title COLLATE NOCASE ASC",
    "pages": "manga.pages DESC",
    "favorites": "manga.favorites DESC",
    "random": "RANDOM()",
}

OPS = {"=": "=", ">": ">", "<": "<", ">=": ">=", "<=": "<="}

CARD_COLS = f"""
    manga.id, manga.source, manga.gallery_id, manga.external_id, manga.parent_external_id,
    manga.media_id, manga.title, manga.pages,
    manga.cover_name, manga.cover_ext, manga.favorites, manga.matched,
    manga.file_size, {ADDED_AT_SQL} AS created_at,
    (SELECT group_concat(t.name) FROM manga_tags mt JOIN tags t ON mt.tag_id = t.id
     WHERE mt.manga_id = manga.id AND t.category = 'language') AS languages,
    (SELECT group_concat(t.name, char(31)) FROM manga_tags mt JOIN tags t ON mt.tag_id = t.id
     WHERE mt.manga_id = manga.id) AS tag_names,
    EXISTS(SELECT 1 FROM userdb.favorites f
           WHERE f.source = manga.source AND f.gallery_id = manga.gallery_id) AS favorite,
    EXISTS(SELECT 1 FROM userdb.pins p
           WHERE p.source = manga.source AND p.gallery_id = manga.gallery_id) AS pinned,
    (SELECT rh.last_page FROM userdb.reading_history rh
     WHERE rh.source = manga.source AND rh.gallery_id = manga.gallery_id) AS read_last_page,
    (SELECT rh.page_count FROM userdb.reading_history rh
     WHERE rh.source = manga.source AND rh.gallery_id = manga.gallery_id) AS read_page_count,
    (SELECT rh.completed_at FROM userdb.reading_history rh
     WHERE rh.source = manga.source AND rh.gallery_id = manga.gallery_id) AS read_completed_at,
    (SELECT si.series_id FROM userdb.series_items si
     WHERE si.source = manga.source AND si.gallery_id = manga.gallery_id) AS series_id,
    (SELECT s.title FROM userdb.series_items si JOIN userdb.series s ON s.id = si.series_id
     WHERE si.source = manga.source AND si.gallery_id = manga.gallery_id) AS series_title,
    (SELECT COUNT(*) FROM userdb.series_items sic
     WHERE sic.series_id = (SELECT si.series_id FROM userdb.series_items si
         WHERE si.source = manga.source AND si.gallery_id = manga.gallery_id)) AS series_chapter_count
"""

# Sort key for "recently added to category"; ordered by the membership timestamp
# for the currently filtered category. Requires a category filter to be active.
CATEGORY_ADDED_SORT = """(SELECT ci.added_at FROM userdb.category_items ci
    WHERE ci.category_id = ? AND ci.source = manga.source AND ci.gallery_id = manga.gallery_id)"""

# Collapses a series to a single Library card: a gallery is shown when it is
# standalone, or when it is its series' representative — the lowest-position
# member that still exists in the index (so a deleted first chapter can't hide
# the whole series). "Set as first" moves a chapter to the front of this order.
SERIES_COLLAPSE_CLAUSE = """ AND (
    NOT EXISTS (SELECT 1 FROM userdb.series_items si
        WHERE si.source = manga.source AND si.gallery_id = manga.gallery_id)
    OR manga.gallery_id = (
        SELECT rep.gallery_id FROM userdb.series_items rep
        JOIN manga m2 ON m2.source = rep.source AND m2.gallery_id = rep.gallery_id
        WHERE rep.series_id = (SELECT si2.series_id FROM userdb.series_items si2
            WHERE si2.source = manga.source AND si2.gallery_id = manga.gallery_id)
        ORDER BY rep.position ASC, rep.gallery_id ASC LIMIT 1)
)"""


@contextmanager
def library_session() -> Iterator[sqlite3.Connection]:
    """Index-DB connection with the user DB attached read-visible as ``userdb``."""
    connection = index_db()
    try:
        connection.execute("ATTACH DATABASE ? AS userdb", (str(MANGA_USER_DB_PATH),))
        yield connection
    finally:
        connection.close()


def _like(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _build_where(
    query: LibraryQuery,
    *,
    language: str | None,
    favorites_only: bool,
    category_id: int | None,
    ignored_tags: list[str] | None,
    show_ignored: bool,
) -> tuple[str, list[Any]]:
    where = "1=1"
    params: list[Any] = []

    if favorites_only:
        where += (
            " AND EXISTS (SELECT 1 FROM userdb.favorites f"
            " WHERE f.source = manga.source AND f.gallery_id = manga.gallery_id)"
        )
    if category_id:
        where += (
            " AND EXISTS (SELECT 1 FROM userdb.category_items ci"
            " WHERE ci.category_id = ? AND ci.source = manga.source AND ci.gallery_id = manga.gallery_id)"
        )
        params.append(category_id)

    normalized_ignored = sorted({tag.strip().lower() for tag in (ignored_tags or []) if tag.strip()})
    if normalized_ignored and not show_ignored:
        placeholders = ",".join("?" for _ in normalized_ignored)
        where += (
            " AND NOT EXISTS (SELECT 1 FROM manga_tags mt JOIN tags tg ON mt.tag_id = tg.id"
            f" WHERE mt.manga_id = manga.id AND lower(tg.name) IN ({placeholders}))"
        )
        params.extend(normalized_ignored)

    language = (language or "all").strip().lower()
    if language and language != "all":
        where += (
            " AND EXISTS (SELECT 1 FROM manga_tags mt JOIN tags tg ON mt.tag_id = tg.id"
            " WHERE mt.manga_id = manga.id AND tg.category = 'language' AND tg.name = ?)"
        )
        params.append(language)

    if query.title:
        like = _like(query.title)
        where += (
            " AND (manga.title LIKE ? ESCAPE '\\' OR manga.title_english LIKE ? ESCAPE '\\'"
            " OR manga.title_japanese LIKE ? ESCAPE '\\' OR manga.title_pretty LIKE ? ESCAPE '\\'"
            " OR CAST(manga.gallery_id AS TEXT) = ?)"
        )
        params.extend([like, like, like, like, query.title])

    if query.jtitle:
        where += (
            " AND (manga.title_japanese LIKE ? ESCAPE '\\' OR manga.title_pretty LIKE ? ESCAPE '\\')"
        )
        params.extend([_like(query.jtitle), _like(query.jtitle)])

    for tag in query.include:
        where += (
            " AND EXISTS (SELECT 1 FROM manga_tags mt JOIN tags tg ON mt.tag_id = tg.id"
            " WHERE mt.manga_id = manga.id AND tg.name = ?)"
        )
        params.append(tag)
    for tag in query.exclude:
        where += (
            " AND NOT EXISTS (SELECT 1 FROM manga_tags mt JOIN tags tg ON mt.tag_id = tg.id"
            " WHERE mt.manga_id = manga.id AND tg.name = ?)"
        )
        params.append(tag)
    for scoped in query.scoped:
        clause = (
            "EXISTS (SELECT 1 FROM manga_tags mt JOIN tags tg ON mt.tag_id = tg.id"
            " WHERE mt.manga_id = manga.id AND tg.category = ? AND tg.name = ?)"
        )
        where += f" AND NOT {clause}" if scoped.negate else f" AND {clause}"
        params.extend([scoped.category, scoped.name])

    if query.pages:
        where += f" AND manga.pages {OPS.get(query.pages.op, '=')} ?"
        params.append(query.pages.value)
    if query.favorites:
        where += f" AND manga.favorites {OPS.get(query.favorites.op, '=')} ?"
        params.append(query.favorites.value)
    if query.uploaded:
        # uploaded:Nd — days ago. ">7d" = older than 7 days; "<7d"/"7d" = within 7 days.
        threshold = int(time.time() * 1000) - query.uploaded.days * 86400000
        direction = {">": "<", ">=": "<=", "<": ">"}.get(query.uploaded.op, ">=")
        where += f" AND manga.upload_date IS NOT NULL AND manga.upload_date {direction} ?"
        params.append(threshold)

    return where, params


def _resolve_order(sort: str, category_id: int | None) -> tuple[str, list[Any]]:
    """Return the ORDER BY fragment (after ``pinned DESC,``) and its bound params.

    ``category_added`` only makes sense with a category filter; without one it
    falls back to the default "recently added" ordering. NULL membership times
    (rows written before the column existed) sort last under the DESC ordering."""
    if sort == "category_added":
        if category_id:
            return f"{CATEGORY_ADDED_SORT} DESC, manga.gallery_id DESC", [category_id]
        return LIBRARY_SORTS["recent"], []
    return LIBRARY_SORTS.get(sort, LIBRARY_SORTS["recent"]), []


def normalize_page_size(requested: int, total: int) -> int:
    """Resolve the Library page size; zero is the explicit all-results sentinel."""
    if requested == 0:
        return max(1, total)
    return max(1, min(200, requested))


def search_library(
    query: LibraryQuery,
    *,
    page: int = 1,
    per_page: int = 60,
    sort: str = "recent",
    language: str | None = None,
    favorites_only: bool = False,
    category_id: int | None = None,
    ignored_tags: list[str] | None = None,
    show_ignored: bool = True,
    collapse_series: bool = True,
) -> dict[str, Any]:
    order, order_params = _resolve_order(sort, category_id)
    with library_session() as connection:
        where, params = _build_where(
            query,
            language=language,
            favorites_only=favorites_only,
            category_id=category_id,
            ignored_tags=ignored_tags,
            show_ignored=show_ignored,
        )
        if collapse_series:
            where += SERIES_COLLAPSE_CLAUSE
        total = connection.execute(
            f"SELECT COUNT(*) FROM manga WHERE {where}", params
        ).fetchone()[0]
        per_page = normalize_page_size(per_page, total)
        page_count = max(1, -(-total // per_page))
        page = min(max(1, page), page_count)
        offset = (page - 1) * per_page
        rows = connection.execute(
            f"SELECT {CARD_COLS} FROM manga WHERE {where}"
            f" ORDER BY pinned DESC, {order} LIMIT ? OFFSET ?",
            (*params, *order_params, per_page, offset),
        ).fetchall()
    return {
        "manga": [dict(row) for row in rows],
        "total": total,
        "page": page,
        "per_page": per_page,
        "page_count": page_count,
    }


def library_stats() -> dict[str, int]:
    with library_session() as connection:
        manga_count = connection.execute("SELECT COUNT(*) FROM manga").fetchone()[0]
        tag_count = connection.execute("SELECT COUNT(*) FROM tags").fetchone()[0]
        favorite_count = connection.execute(
            "SELECT COUNT(*) FROM userdb.favorites f WHERE EXISTS"
            " (SELECT 1 FROM manga m WHERE m.source = f.source AND m.gallery_id = f.gallery_id)"
        ).fetchone()[0]
    return {"manga_count": manga_count, "tag_count": tag_count, "favorite_count": favorite_count}


def recent_downloads(
    *,
    limit: int = 6,
    offset: int = 0,
    ignored_tags: list[str] | None = None,
    show_ignored: bool = True,
) -> dict[str, Any]:
    """Return local manga strictly by preserved first-added time, without pin promotion."""
    limit = max(1, min(200, limit))
    offset = max(0, offset)
    with library_session() as connection:
        where, params = _build_where(
            LibraryQuery(),
            language=None,
            favorites_only=False,
            category_id=None,
            ignored_tags=ignored_tags,
            show_ignored=show_ignored,
        )
        total = connection.execute(f"SELECT COUNT(*) FROM manga WHERE {where}", params).fetchone()[0]
        rows = connection.execute(
            f"SELECT {CARD_COLS} FROM manga WHERE {where}"
            f" ORDER BY {ADDED_AT_SQL} DESC, manga.gallery_id DESC LIMIT ? OFFSET ?",
            (*params, limit, offset),
        ).fetchall()
    return {"manga": [dict(row) for row in rows], "total": total, "limit": limit, "offset": offset}


def save_reading_progress(
    gallery_id: int,
    *,
    title: str,
    cover_path: str | None,
    last_page: int,
    page_count: int,
    source: str = "nhentai",
) -> dict[str, Any]:
    """Upsert durable resume state without touching the disposable manga index."""
    now = int(time.time() * 1000)
    page_count = max(0, page_count)
    last_page = max(0, min(last_page, max(0, page_count - 1)))
    cleaned_title = (title or f"#{gallery_id}").strip()[:500] or f"#{gallery_id}"
    cleaned_cover = (cover_path or "").strip()[:1000] or None
    completed_at = now if page_count > 0 and last_page >= page_count - 1 else None
    with user_session() as user:
        user.execute(
            "INSERT INTO reading_history"
            " (source, gallery_id, title, cover_path, last_page, page_count, started_at, last_read_at, completed_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"
            " ON CONFLICT(source, gallery_id) DO UPDATE SET"
            " title = excluded.title,"
            " cover_path = COALESCE(excluded.cover_path, reading_history.cover_path),"
            " last_page = excluded.last_page,"
            " page_count = excluded.page_count,"
            " last_read_at = excluded.last_read_at,"
            " completed_at = COALESCE(excluded.completed_at, reading_history.completed_at)",
            (
                source,
                gallery_id,
                cleaned_title,
                cleaned_cover,
                last_page,
                page_count,
                now,
                now,
                completed_at,
            ),
        )
    return reading_progress(gallery_id, source=source) or {}


def reading_progress(gallery_id: int, source: str = "nhentai") -> dict[str, Any] | None:
    with user_session() as user:
        row = user.execute(
            "SELECT source, gallery_id, title, cover_path, last_page, page_count,"
            " started_at, last_read_at, completed_at FROM reading_history"
            " WHERE source = ? AND gallery_id = ?",
            (source, gallery_id),
        ).fetchone()
    return dict(row) if row is not None else None


def reading_history(*, limit: int = 60, offset: int = 0) -> dict[str, Any]:
    limit = max(1, min(200, limit))
    offset = max(0, offset)
    with library_session() as connection:
        total = connection.execute("SELECT COUNT(*) FROM userdb.reading_history").fetchone()[0]
        rows = connection.execute(
            "SELECT h.source, h.gallery_id, identity.external_id, h.title, h.cover_path, h.last_page, h.page_count,"
            " h.started_at, h.last_read_at, h.completed_at, manga.id AS local_manga_id,"
            " manga.cover_name, manga.cover_ext"
            " FROM userdb.reading_history h"
            " LEFT JOIN manga ON manga.source = h.source AND manga.gallery_id = h.gallery_id"
            " LEFT JOIN userdb.remote_identities identity"
            " ON identity.source = h.source AND identity.gallery_id = h.gallery_id"
            " ORDER BY h.last_read_at DESC, h.gallery_id DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
    items = []
    for row in rows:
        item = dict(row)
        item["downloaded"] = item["local_manga_id"] is not None
        items.append(item)
    return {"items": items, "total": total, "limit": limit, "offset": offset}


def tags_for_manga(connection: sqlite3.Connection, manga_id: int) -> list[dict[str, str]]:
    rows = connection.execute(
        "SELECT t.name, t.category FROM manga_tags mt JOIN tags t ON mt.tag_id = t.id"
        " WHERE mt.manga_id = ? ORDER BY t.category, t.name",
        (manga_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def get_manga_by_id(manga_id: int) -> dict[str, Any] | None:
    with library_session() as connection:
        row = connection.execute(
            f"SELECT {CARD_COLS}, manga.title_english, manga.title_japanese, manga.title_pretty,"
            " manga.scanlator, manga.upload_date, manga.raw_json, manga.file_path, manga.root_id"
            " FROM manga WHERE manga.id = ?",
            (manga_id,),
        ).fetchone()
        if row is None:
            return None
        detail = dict(row)
        detail["tags"] = tags_for_manga(connection, manga_id)
    return detail


def get_manga_by_gallery_id(gallery_id: int, source: str = "nhentai") -> dict[str, Any] | None:
    with library_session() as connection:
        row = connection.execute(
            f"SELECT {CARD_COLS} FROM manga WHERE manga.source = ? AND manga.gallery_id = ?",
            (source, gallery_id),
        ).fetchone()
    return dict(row) if row is not None else None


def source_for_gallery_id(gallery_id: int) -> str:
    """Resolve the provider of a local key; positive legacy IDs stay nHentai."""
    with library_session() as connection:
        row = connection.execute(
            "SELECT source FROM manga WHERE gallery_id = ? ORDER BY id LIMIT 1",
            (gallery_id,),
        ).fetchone()
        if row is None:
            row = connection.execute(
                "SELECT source FROM userdb.remote_identities WHERE gallery_id = ?",
                (gallery_id,),
            ).fetchone()
    return str(row[0]) if row is not None else "nhentai"


def get_manga_by_external_id(external_id: str, source: str) -> dict[str, Any] | None:
    with library_session() as connection:
        row = connection.execute(
            f"SELECT {CARD_COLS} FROM manga WHERE manga.source = ? AND manga.external_id = ?",
            (source, external_id),
        ).fetchone()
    return dict(row) if row is not None else None


def downloaded_external_ids(external_ids: list[str], source: str) -> set[str]:
    unique = sorted({value for value in external_ids if value})
    if not unique:
        return set()
    placeholders = ",".join("?" for _ in unique)
    with library_session() as connection:
        rows = connection.execute(
            f"SELECT external_id FROM manga WHERE source = ?"
            f" AND external_id IN ({placeholders})",
            (source, *unique),
        ).fetchall()
    return {str(row[0]) for row in rows if row[0] is not None}


def downloaded_parent_counts(parent_ids: list[str], source: str) -> dict[str, int]:
    unique = sorted({value for value in parent_ids if value})
    if not unique:
        return {}
    placeholders = ",".join("?" for _ in unique)
    with library_session() as connection:
        rows = connection.execute(
            "SELECT parent_external_id, COUNT(*) AS chapter_count FROM manga"
            f" WHERE source = ? AND parent_external_id IN ({placeholders})"
            " GROUP BY parent_external_id",
            (source, *unique),
        ).fetchall()
    return {str(row["parent_external_id"]): int(row["chapter_count"]) for row in rows}


def cover_info_for_gallery(gallery_id: int, source: str = "nhentai") -> dict[str, Any] | None:
    with library_session() as connection:
        row = connection.execute(
            "SELECT id, cover_name, file_path FROM manga WHERE source = ? AND gallery_id = ?",
            (source, gallery_id),
        ).fetchone()
    return dict(row) if row is not None else None


def file_path_for_gallery(gallery_id: int, source: str = "nhentai") -> str | None:
    with library_session() as connection:
        row = connection.execute(
            "SELECT file_path FROM manga WHERE source = ? AND gallery_id = ?",
            (source, gallery_id),
        ).fetchone()
    return row[0] if row is not None else None


def downloaded_gallery_ids(gallery_ids: list[int], source: str = "nhentai") -> set[int]:
    if not gallery_ids:
        return set()
    placeholders = ",".join("?" for _ in gallery_ids)
    with library_session() as connection:
        rows = connection.execute(
            f"SELECT gallery_id FROM manga WHERE source = ? AND gallery_id IN ({placeholders})",
            (source, *gallery_ids),
        ).fetchall()
    return {row[0] for row in rows}


def tag_info_by_nh_ids(nh_ids: list[int]) -> dict[int, dict[str, str]]:
    unique = sorted({nh_id for nh_id in nh_ids if isinstance(nh_id, int)})
    if not unique:
        return {}
    placeholders = ",".join("?" for _ in unique)
    with library_session() as connection:
        rows = connection.execute(
            f"SELECT nh_id, name, category FROM tags WHERE nh_id IN ({placeholders})", unique
        ).fetchall()
    return {row["nh_id"]: {"name": row["name"], "category": row["category"]} for row in rows}


def top_tags(limit: int = 60) -> list[dict[str, Any]]:
    with library_session() as connection:
        rows = connection.execute(
            "SELECT name, category, manga_count AS count FROM tags"
            " WHERE manga_count > 0 ORDER BY manga_count DESC, name ASC LIMIT ?",
            (max(1, min(500, limit)),),
        ).fetchall()
    return [dict(row) for row in rows]


def downloaded_tag_directory(sort: str = "popular") -> list[dict[str, Any]]:
    """Return every downloaded generic tag with its exact Library-filter count."""
    with library_session() as connection:
        rows = connection.execute(
            "WITH directory AS ("
            " SELECT lower(name) AS name_key, MIN(name) AS name"
            " FROM tags WHERE category = 'tag' GROUP BY lower(name)"
            ")"
            " SELECT directory.name, directory.name_key,"
            " COUNT(DISTINCT m.id) AS downloaded_count"
            " FROM directory"
            " JOIN tags matched ON lower(matched.name) = directory.name_key"
            " JOIN manga_tags mt ON mt.tag_id = matched.id"
            " JOIN manga m ON m.id = mt.manga_id"
            " GROUP BY directory.name_key HAVING downloaded_count > 0",
        ).fetchall()
    items = [
        {
            "name": str(row["name"]),
            "slug": str(row["name_key"]).replace(" ", "-"),
            "count": int(row["downloaded_count"]),
        }
        for row in rows
    ]
    if sort == "a-z":
        items.sort(key=lambda item: (str(item["name"]).casefold(), str(item["slug"])))
    else:
        items.sort(
            key=lambda item: (-int(item["count"]), str(item["name"]).casefold(), str(item["slug"]))
        )
    return items


def suggest_tags(query: str, limit: int = 12) -> list[dict[str, Any]]:
    lowered = (query or "").lower()
    with library_session() as connection:
        rows = connection.execute(
            "SELECT name, category, manga_count AS count FROM tags"
            " WHERE name LIKE ? AND manga_count > 0"
            " ORDER BY (name = ?) DESC, manga_count DESC, name ASC LIMIT ?",
            (f"%{lowered}%", lowered, max(1, min(50, limit))),
        ).fetchall()
    return [dict(row) for row in rows]


# ---- User-data toggles (favorites / pins), keyed by (source, gallery_id) ----

def toggle_favorite(gallery_id: int, source: str = "nhentai") -> bool:
    with user_session() as user:
        existing = user.execute(
            "SELECT 1 FROM favorites WHERE source = ? AND gallery_id = ?", (source, gallery_id)
        ).fetchone()
        if existing:
            user.execute(
                "DELETE FROM favorites WHERE source = ? AND gallery_id = ?", (source, gallery_id)
            )
            return False
        user.execute(
            "INSERT INTO favorites (source, gallery_id, created_at) VALUES (?, ?, ?)",
            (source, gallery_id, int(time.time() * 1000)),
        )
        return True


def toggle_pinned(gallery_id: int, source: str = "nhentai") -> bool:
    with user_session() as user:
        existing = user.execute(
            "SELECT 1 FROM pins WHERE source = ? AND gallery_id = ?", (source, gallery_id)
        ).fetchone()
        if existing:
            user.execute("DELETE FROM pins WHERE source = ? AND gallery_id = ?", (source, gallery_id))
            return False
        user.execute(
            "INSERT INTO pins (source, gallery_id, created_at) VALUES (?, ?, ?)",
            (source, gallery_id, int(time.time() * 1000)),
        )
        return True


# ---- Categories (Tachiyomi-style; separate from Danbooru collections) ----

def list_categories() -> list[dict[str, Any]]:
    with user_session() as user:
        rows = user.execute(
            "SELECT c.id, c.name, c.position,"
            " (SELECT COUNT(*) FROM category_items ci WHERE ci.category_id = c.id) AS manga_count"
            " FROM categories c ORDER BY c.position ASC, c.name COLLATE NOCASE ASC"
        ).fetchall()
    return [dict(row) for row in rows]


def create_category(name: str) -> dict[str, Any]:
    cleaned = (name or "").strip()
    if not cleaned:
        return {"ok": False, "error": "Empty name"}
    if len(cleaned) > 60:
        return {"ok": False, "error": "Name too long"}
    try:
        with user_session() as user:
            maximum = user.execute("SELECT COALESCE(MAX(position), 0) FROM categories").fetchone()[0]
            user.execute(
                "INSERT INTO categories (name, position, created_at) VALUES (?, ?, ?)",
                (cleaned, maximum + 1, int(time.time() * 1000)),
            )
        return {"ok": True}
    except sqlite3.IntegrityError:
        return {"ok": False, "error": "A category with that name already exists"}


def delete_category(category_id: int) -> None:
    # The membership rows go too; the manga themselves are untouched.
    with user_session() as user:
        user.execute("DELETE FROM category_items WHERE category_id = ?", (category_id,))
        user.execute("DELETE FROM categories WHERE id = ?", (category_id,))


def category_ids_for_gallery(gallery_id: int, source: str = "nhentai") -> list[int]:
    with user_session() as user:
        rows = user.execute(
            "SELECT category_id FROM category_items WHERE source = ? AND gallery_id = ?",
            (source, gallery_id),
        ).fetchall()
    return [row[0] for row in rows]


def toggle_category_membership(gallery_id: int, category_id: int, source: str = "nhentai") -> bool:
    with user_session() as user:
        existing = user.execute(
            "SELECT 1 FROM category_items WHERE category_id = ? AND source = ? AND gallery_id = ?",
            (category_id, source, gallery_id),
        ).fetchone()
        if existing:
            user.execute(
                "DELETE FROM category_items WHERE category_id = ? AND source = ? AND gallery_id = ?",
                (category_id, source, gallery_id),
            )
            return False
        user.execute(
            "INSERT INTO category_items (category_id, source, gallery_id, added_at)"
            " VALUES (?, ?, ?, ?)",
            (category_id, source, gallery_id, int(time.time() * 1000)),
        )
        return True


# ---- Series (ordered multi-chapter works; one series per gallery) ----

def _prune_empty_series(user: sqlite3.Connection) -> None:
    """Drop any series left with no chapters, so moves never orphan a group."""
    user.execute("DELETE FROM series WHERE id NOT IN (SELECT series_id FROM series_items)")


def list_series() -> list[dict[str, Any]]:
    """Every series with its chapter count and representative cover gallery."""
    with library_session() as connection:
        rows = connection.execute(
            "SELECT s.id, s.title, s.created_at,"
            " (SELECT COUNT(*) FROM userdb.series_items si WHERE si.series_id = s.id) AS chapter_count,"
            " (SELECT rep.gallery_id FROM userdb.series_items rep"
            "  JOIN manga m2 ON m2.source = rep.source AND m2.gallery_id = rep.gallery_id"
            "  WHERE rep.series_id = s.id ORDER BY rep.position ASC, rep.gallery_id ASC LIMIT 1)"
            "  AS cover_gallery_id"
            " FROM userdb.series s ORDER BY s.title COLLATE NOCASE ASC"
        ).fetchall()
    return [dict(row) for row in rows]


def series_detail(series_id: int) -> dict[str, Any] | None:
    """Series header plus its chapters as full Library cards, in reading order."""
    with library_session() as connection:
        header = connection.execute(
            "SELECT id, title, created_at FROM userdb.series WHERE id = ?", (series_id,)
        ).fetchone()
        if header is None:
            return None
        rows = connection.execute(
            f"SELECT {CARD_COLS}, si.position AS series_position FROM manga"
            " JOIN userdb.series_items si ON si.source = manga.source AND si.gallery_id = manga.gallery_id"
            " WHERE si.series_id = ? ORDER BY si.position ASC, manga.gallery_id ASC",
            (series_id,),
        ).fetchall()
    detail = dict(header)
    detail["chapters"] = [dict(row) for row in rows]
    return detail


def create_series(title: str, gallery_ids: list[int], source: str = "nhentai") -> dict[str, Any]:
    cleaned = (title or "").strip()[:200]
    if not cleaned:
        return {"ok": False, "error": "Empty title"}
    now = int(time.time() * 1000)
    with user_session() as user:
        cursor = user.execute("INSERT INTO series (title, created_at) VALUES (?, ?)", (cleaned, now))
        series_id = int(cursor.lastrowid)
        for position, gallery_id in enumerate(gallery_ids):
            user.execute(
                "DELETE FROM series_items WHERE source = ? AND gallery_id = ?", (source, gallery_id)
            )
            user.execute(
                "INSERT INTO series_items (series_id, source, gallery_id, position, added_at)"
                " VALUES (?, ?, ?, ?, ?)",
                (series_id, source, gallery_id, position, now),
            )
        _prune_empty_series(user)
    return {"ok": True, "series_id": series_id}


def add_to_series(series_id: int, gallery_id: int, source: str = "nhentai") -> dict[str, Any]:
    """Append a chapter to a series, moving it out of any series it was in."""
    with user_session() as user:
        if user.execute("SELECT 1 FROM series WHERE id = ?", (series_id,)).fetchone() is None:
            return {"ok": False, "error": "Series not found"}
        user.execute(
            "DELETE FROM series_items WHERE source = ? AND gallery_id = ?", (source, gallery_id)
        )
        next_position = user.execute(
            "SELECT COALESCE(MAX(position), -1) + 1 FROM series_items WHERE series_id = ?",
            (series_id,),
        ).fetchone()[0]
        user.execute(
            "INSERT INTO series_items (series_id, source, gallery_id, position, added_at)"
            " VALUES (?, ?, ?, ?, ?)",
            (series_id, source, gallery_id, next_position, int(time.time() * 1000)),
        )
        _prune_empty_series(user)
    return {"ok": True, "series_id": series_id}


def remove_from_series(gallery_id: int, source: str = "nhentai") -> dict[str, Any]:
    with user_session() as user:
        user.execute(
            "DELETE FROM series_items WHERE source = ? AND gallery_id = ?", (source, gallery_id)
        )
        _prune_empty_series(user)
    return {"ok": True}


def set_series_first(gallery_id: int, source: str = "nhentai") -> dict[str, Any]:
    """Make a chapter the series' representative (its cover shows in the grid)."""
    with user_session() as user:
        row = user.execute(
            "SELECT series_id FROM series_items WHERE source = ? AND gallery_id = ?",
            (source, gallery_id),
        ).fetchone()
        if row is None:
            return {"ok": False, "error": "Not in a series"}
        minimum = user.execute(
            "SELECT COALESCE(MIN(position), 0) FROM series_items WHERE series_id = ?", (row[0],)
        ).fetchone()[0]
        user.execute(
            "UPDATE series_items SET position = ? WHERE source = ? AND gallery_id = ?",
            (minimum - 1, source, gallery_id),
        )
    return {"ok": True}


def rename_series(series_id: int, title: str) -> dict[str, Any]:
    cleaned = (title or "").strip()[:200]
    if not cleaned:
        return {"ok": False, "error": "Empty title"}
    with user_session() as user:
        user.execute("UPDATE series SET title = ? WHERE id = ?", (cleaned, series_id))
    return {"ok": True}


def reorder_series(series_id: int, ordered_gallery_ids: list[int], source: str = "nhentai") -> dict[str, Any]:
    with user_session() as user:
        for position, gallery_id in enumerate(ordered_gallery_ids):
            user.execute(
                "UPDATE series_items SET position = ?"
                " WHERE series_id = ? AND source = ? AND gallery_id = ?",
                (position, series_id, source, gallery_id),
            )
    return {"ok": True}


def delete_series(series_id: int) -> dict[str, Any]:
    """Ungroup: the series and its membership rows go; the galleries remain."""
    with user_session() as user:
        user.execute("DELETE FROM series_items WHERE series_id = ?", (series_id,))
        user.execute("DELETE FROM series WHERE id = ?", (series_id,))
    return {"ok": True}
