"""Rebuildable Karaoke index and additive precious user state."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Any, Generator

from modules.karaoke import lyrics as lyric_tools


CATALOG_SCHEMA = """
CREATE TABLE IF NOT EXISTS karaoke_items (
    item_id TEXT PRIMARY KEY,
    provider TEXT NOT NULL,
    provider_id TEXT NOT NULL,
    title TEXT NOT NULL,
    subtitle TEXT NOT NULL DEFAULT '',
    year INTEGER,
    duration REAL,
    primary_video TEXT NOT NULL,
    thumbnail TEXT,
    metadata_path TEXT NOT NULL,
    receipt_path TEXT NOT NULL,
    primary_sha256 TEXT NOT NULL,
    external_source_id TEXT,
    external_relative_path TEXT,
    metadata_json TEXT NOT NULL,
    added_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(provider, provider_id)
);
CREATE INDEX IF NOT EXISTS idx_karaoke_items_title
    ON karaoke_items(title COLLATE NOCASE);

CREATE TABLE IF NOT EXISTS karaoke_tags (
    item_id TEXT NOT NULL REFERENCES karaoke_items(item_id) ON DELETE CASCADE,
    category TEXT NOT NULL,
    name TEXT NOT NULL,
    PRIMARY KEY (item_id, category, name)
);

CREATE TABLE IF NOT EXISTS karaoke_lyrics (
    lyric_id TEXT PRIMARY KEY,
    item_id TEXT NOT NULL REFERENCES karaoke_items(item_id) ON DELETE CASCADE,
    label TEXT NOT NULL,
    language TEXT NOT NULL DEFAULT '',
    format TEXT NOT NULL,
    source_kind TEXT NOT NULL,
    relative_path TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    cues_json TEXT NOT NULL DEFAULT '[]',
    added_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(item_id, relative_path)
);

CREATE TABLE IF NOT EXISTS karaoke_plans (
    token TEXT PRIMARY KEY,
    provider_id TEXT NOT NULL,
    selection_sha256 TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    expires_at TEXT NOT NULL,
    consumed_at TEXT
);

CREATE TABLE IF NOT EXISTS karaoke_jobs (
    job_id TEXT PRIMARY KEY,
    plan_token TEXT NOT NULL,
    provider_id TEXT NOT NULL,
    status TEXT NOT NULL,
    phase TEXT NOT NULL,
    progress REAL NOT NULL DEFAULT 0,
    downloaded_bytes INTEGER NOT NULL DEFAULT 0,
    total_bytes INTEGER,
    error TEXT,
    item_id TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


USER_SCHEMA = """
CREATE TABLE IF NOT EXISTS karaoke_favorites (
    item_key TEXT PRIMARY KEY,
    file_sha256 TEXT,
    added_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS karaoke_playlists (
    playlist_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS karaoke_playlist_items (
    playlist_id INTEGER NOT NULL REFERENCES karaoke_playlists(playlist_id)
        ON DELETE CASCADE,
    item_key TEXT NOT NULL,
    file_sha256 TEXT,
    position INTEGER NOT NULL,
    added_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (playlist_id, item_key)
);
CREATE INDEX IF NOT EXISTS idx_karaoke_playlist_position
    ON karaoke_playlist_items(playlist_id, position);

CREATE TABLE IF NOT EXISTS karaoke_playback_state (
    item_key TEXT PRIMARY KEY,
    file_sha256 TEXT,
    position_seconds REAL NOT NULL DEFAULT 0,
    duration_seconds REAL,
    completed INTEGER NOT NULL DEFAULT 0,
    lyric_id TEXT,
    lyric_offset_seconds REAL NOT NULL DEFAULT 0,
    repeat_mode TEXT NOT NULL DEFAULT 'off',
    shuffle INTEGER NOT NULL DEFAULT 0,
    last_played_at TEXT,
    play_count INTEGER NOT NULL DEFAULT 0
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def open_catalog(path: Path) -> Generator[sqlite3.Connection, None, None]:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA journal_mode=WAL")
        connection.executescript(CATALOG_SCHEMA)
        columns = {
            row["name"]
            for row in connection.execute(
                "PRAGMA table_info(karaoke_items)"
            ).fetchall()
        }
        if "external_source_id" not in columns:
            connection.execute(
                "ALTER TABLE karaoke_items ADD COLUMN external_source_id TEXT"
            )
        if "external_relative_path" not in columns:
            connection.execute(
                "ALTER TABLE karaoke_items ADD COLUMN external_relative_path TEXT"
            )
        connection.commit()
        yield connection
    finally:
        connection.close()


def ensure_user_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(USER_SCHEMA)
    playback_columns = {
        row["name"]
        for row in connection.execute(
            "PRAGMA table_info(karaoke_playback_state)"
        ).fetchall()
    }
    if "play_count" not in playback_columns:
        connection.execute(
            "ALTER TABLE karaoke_playback_state "
            "ADD COLUMN play_count INTEGER NOT NULL DEFAULT 0"
        )
    connection.commit()


def recover_interrupted_jobs(connection: sqlite3.Connection) -> int:
    changed = connection.execute(
        "UPDATE karaoke_jobs SET status='interrupted', phase='interrupted', "
        "updated_at=? WHERE status IN ('queued', 'running')",
        (_now(),),
    ).rowcount
    connection.commit()
    return max(changed, 0)


def store_plan(
    connection: sqlite3.Connection,
    *,
    token: str,
    provider_id: str,
    selection_sha256: str,
    payload: dict[str, Any],
    expires_at: str,
) -> None:
    connection.execute(
        "INSERT INTO karaoke_plans"
        "(token, provider_id, selection_sha256, payload_json, expires_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (
            token,
            provider_id,
            selection_sha256,
            json.dumps(payload, ensure_ascii=False, sort_keys=True),
            expires_at,
        ),
    )
    connection.commit()


def get_plan(
    connection: sqlite3.Connection,
    token: str,
    *,
    allow_consumed: bool = False,
) -> dict[str, Any] | None:
    row = connection.execute(
        "SELECT * FROM karaoke_plans WHERE token=?", (token,)
    ).fetchone()
    if row is None or (row["consumed_at"] and not allow_consumed):
        return None
    value = dict(row)
    value["payload"] = _loads(value.pop("payload_json"), {})
    return value


def consume_plan(connection: sqlite3.Connection, token: str) -> bool:
    changed = connection.execute(
        "UPDATE karaoke_plans SET consumed_at=? "
        "WHERE token=? AND consumed_at IS NULL",
        (_now(), token),
    ).rowcount
    connection.commit()
    return changed == 1


def create_job(
    connection: sqlite3.Connection,
    *,
    job_id: str,
    plan_token: str,
    provider_id: str,
) -> dict[str, Any]:
    connection.execute(
        "INSERT INTO karaoke_jobs"
        "(job_id, plan_token, provider_id, status, phase) "
        "VALUES (?, ?, ?, 'queued', 'queued')",
        (job_id, plan_token, provider_id),
    )
    connection.commit()
    value = get_job(connection, job_id)
    assert value is not None
    return value


def update_job(
    connection: sqlite3.Connection,
    job_id: str,
    *,
    status: str | None = None,
    phase: str | None = None,
    progress: float | None = None,
    downloaded_bytes: int | None = None,
    total_bytes: int | None = None,
    error: str | None = None,
    item_id: str | None = None,
) -> dict[str, Any]:
    assignments = ["updated_at=?"]
    parameters: list[Any] = [_now()]
    for name, value in (
        ("status", status),
        ("phase", phase),
        ("progress", progress),
        ("downloaded_bytes", downloaded_bytes),
        ("total_bytes", total_bytes),
        ("error", error),
        ("item_id", item_id),
    ):
        if value is not None:
            assignments.append(f"{name}=?")
            parameters.append(value)
    parameters.append(job_id)
    connection.execute(
        f"UPDATE karaoke_jobs SET {', '.join(assignments)} WHERE job_id=?",
        parameters,
    )
    connection.commit()
    value = get_job(connection, job_id)
    if value is None:
        raise ValueError("Unknown Karaoke job")
    return value


def get_job(connection: sqlite3.Connection, job_id: str) -> dict[str, Any] | None:
    row = connection.execute(
        "SELECT * FROM karaoke_jobs WHERE job_id=?", (job_id,)
    ).fetchone()
    return dict(row) if row is not None else None


def list_jobs(connection: sqlite3.Connection, limit: int = 25) -> list[dict[str, Any]]:
    return [
        dict(row)
        for row in connection.execute(
            "SELECT * FROM karaoke_jobs ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    ]


def _loads(value: str | None, fallback: Any) -> Any:
    if not value:
        return fallback
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return fallback


def _read_cues(value: str | None) -> list[dict[str, Any]]:
    loaded = _loads(value, [])
    if not isinstance(loaded, list):
        return []
    cues: list[dict[str, Any]] = []
    for entry in loaded:
        if not isinstance(entry, dict):
            continue
        cue = dict(entry)
        cue["text"] = lyric_tools.plain_text(cue.get("text", ""))
        if cue.get("translation") is not None:
            cue["translation"] = lyric_tools.plain_text(cue["translation"])
        cues.append(cue)
    return cues


def item_from_row(connection: sqlite3.Connection, row: sqlite3.Row) -> dict[str, Any]:
    item = dict(row)
    item["metadata"] = _loads(item.pop("metadata_json"), {})
    item["tags"] = {}
    for tag in connection.execute(
        "SELECT category, name FROM karaoke_tags WHERE item_id=? "
        "ORDER BY category, name COLLATE NOCASE",
        (item["item_id"],),
    ).fetchall():
        item["tags"].setdefault(tag["category"], []).append(tag["name"])
    item["lyrics"] = [
        {
            **dict(lyric),
            "cues": _read_cues(lyric["cues_json"]),
        }
        for lyric in connection.execute(
            "SELECT lyric_id, label, language, format, source_kind, relative_path, "
            "sha256, cues_json, added_at FROM karaoke_lyrics WHERE item_id=? "
            "ORDER BY added_at, label COLLATE NOCASE",
            (item["item_id"],),
        ).fetchall()
    ]
    for lyric in item["lyrics"]:
        lyric.pop("cues_json", None)
    return item


def list_items(
    connection: sqlite3.Connection,
    *,
    query: str = "",
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    pattern = f"%{query.strip()}%"
    rows = connection.execute(
        "SELECT * FROM karaoke_items "
        "WHERE (?='' OR title LIKE ? COLLATE NOCASE OR subtitle LIKE ? COLLATE NOCASE) "
        "ORDER BY added_at DESC, title COLLATE NOCASE LIMIT ? OFFSET ?",
        (query.strip(), pattern, pattern, limit, offset),
    ).fetchall()
    return [item_from_row(connection, row) for row in rows]


def get_item(connection: sqlite3.Connection, item_id: str) -> dict[str, Any] | None:
    row = connection.execute(
        "SELECT * FROM karaoke_items WHERE item_id=?", (item_id,)
    ).fetchone()
    return item_from_row(connection, row) if row is not None else None


def upsert_item(
    connection: sqlite3.Connection,
    item: dict[str, Any],
    tags: dict[str, list[str]],
    lyrics: list[dict[str, Any]],
) -> None:
    connection.execute(
        """INSERT INTO karaoke_items
           (item_id, provider, provider_id, title, subtitle, year, duration,
            primary_video, thumbnail, metadata_path, receipt_path,
            primary_sha256, external_source_id, external_relative_path,
            metadata_json, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(item_id) DO UPDATE SET
             title=excluded.title, subtitle=excluded.subtitle, year=excluded.year,
             duration=excluded.duration, primary_video=excluded.primary_video,
             thumbnail=excluded.thumbnail, metadata_path=excluded.metadata_path,
             receipt_path=excluded.receipt_path,
             primary_sha256=excluded.primary_sha256,
             external_source_id=excluded.external_source_id,
             external_relative_path=excluded.external_relative_path,
             metadata_json=excluded.metadata_json, updated_at=excluded.updated_at""",
        (
            item["item_id"],
            item["provider"],
            item["provider_id"],
            item["title"],
            item.get("subtitle", ""),
            item.get("year"),
            item.get("duration"),
            item["primary_video"],
            item.get("thumbnail"),
            item["metadata_path"],
            item["receipt_path"],
            item["primary_sha256"],
            item.get("external_source_id"),
            item.get("external_relative_path"),
            json.dumps(item.get("metadata", {}), ensure_ascii=False, sort_keys=True),
            _now(),
        ),
    )
    connection.execute("DELETE FROM karaoke_tags WHERE item_id=?", (item["item_id"],))
    for category, names in tags.items():
        for name in names:
            connection.execute(
                "INSERT OR IGNORE INTO karaoke_tags(item_id, category, name) "
                "VALUES (?, ?, ?)",
                (item["item_id"], category, name),
            )
    for lyric in lyrics:
        connection.execute(
            """INSERT INTO karaoke_lyrics
               (lyric_id, item_id, label, language, format, source_kind,
                relative_path, sha256, cues_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(lyric_id) DO UPDATE SET
                 label=excluded.label, language=excluded.language,
                 format=excluded.format, source_kind=excluded.source_kind,
                 relative_path=excluded.relative_path, sha256=excluded.sha256,
                 cues_json=excluded.cues_json""",
            (
                lyric["lyric_id"],
                item["item_id"],
                lyric["label"],
                lyric.get("language", ""),
                lyric["format"],
                lyric["source_kind"],
                lyric["relative_path"],
                lyric["sha256"],
                json.dumps(lyric.get("cues", []), ensure_ascii=False),
            ),
        )
    connection.commit()


def add_lyric(
    connection: sqlite3.Connection,
    *,
    item_id: str,
    lyric: dict[str, Any],
) -> None:
    if get_item(connection, item_id) is None:
        raise ValueError("Unknown karaoke item")
    connection.execute(
        """INSERT INTO karaoke_lyrics
           (lyric_id, item_id, label, language, format, source_kind,
            relative_path, sha256, cues_json)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            lyric["lyric_id"],
            item_id,
            lyric["label"],
            lyric.get("language", ""),
            lyric["format"],
            lyric["source_kind"],
            lyric["relative_path"],
            lyric["sha256"],
            json.dumps(lyric.get("cues", []), ensure_ascii=False),
        ),
    )
    connection.commit()


def favorite_ids(user_connection: sqlite3.Connection) -> set[str]:
    ensure_user_schema(user_connection)
    return {
        row["item_key"]
        for row in user_connection.execute(
            "SELECT item_key FROM karaoke_favorites"
        ).fetchall()
    }


def set_favorite(
    user_connection: sqlite3.Connection,
    item_key: str,
    file_sha256: str | None,
    favorite: bool,
) -> bool:
    ensure_user_schema(user_connection)
    if favorite:
        user_connection.execute(
            "INSERT INTO karaoke_favorites(item_key, file_sha256) VALUES (?, ?) "
            "ON CONFLICT(item_key) DO UPDATE SET file_sha256=excluded.file_sha256",
            (item_key, file_sha256),
        )
    else:
        user_connection.execute(
            "DELETE FROM karaoke_favorites WHERE item_key=?", (item_key,)
        )
    user_connection.commit()
    return favorite


def list_playlists(user_connection: sqlite3.Connection) -> list[dict[str, Any]]:
    ensure_user_schema(user_connection)
    playlists = []
    for row in user_connection.execute(
        "SELECT playlist_id, name, description, created_at, updated_at "
        "FROM karaoke_playlists ORDER BY updated_at DESC, name COLLATE NOCASE"
    ).fetchall():
        item = dict(row)
        item["items"] = [
            dict(child)
            for child in user_connection.execute(
                "SELECT item_key, file_sha256, position, added_at "
                "FROM karaoke_playlist_items WHERE playlist_id=? ORDER BY position",
                (row["playlist_id"],),
            ).fetchall()
        ]
        playlists.append(item)
    return playlists


def create_playlist(
    user_connection: sqlite3.Connection, name: str, description: str
) -> dict[str, Any]:
    ensure_user_schema(user_connection)
    clean = name.strip()
    if not clean:
        raise ValueError("Playlist name is required")
    cursor = user_connection.execute(
        "INSERT INTO karaoke_playlists(name, description) VALUES (?, ?)",
        (clean, description.strip()),
    )
    user_connection.commit()
    playlist_id = int(cursor.lastrowid)
    return next(
        value
        for value in list_playlists(user_connection)
        if value["playlist_id"] == playlist_id
    )


def update_playlist(
    user_connection: sqlite3.Connection,
    playlist_id: int,
    name: str,
    description: str,
) -> dict[str, Any]:
    ensure_user_schema(user_connection)
    clean = name.strip()
    if not clean:
        raise ValueError("Playlist name is required")
    changed = user_connection.execute(
        "UPDATE karaoke_playlists SET name=?, description=?, updated_at=? "
        "WHERE playlist_id=?",
        (clean, description.strip(), _now(), playlist_id),
    ).rowcount
    if not changed:
        raise ValueError("Unknown playlist")
    user_connection.commit()
    return next(
        value
        for value in list_playlists(user_connection)
        if value["playlist_id"] == playlist_id
    )


def delete_playlist(user_connection: sqlite3.Connection, playlist_id: int) -> bool:
    ensure_user_schema(user_connection)
    changed = user_connection.execute(
        "DELETE FROM karaoke_playlists WHERE playlist_id=?",
        (playlist_id,),
    ).rowcount
    user_connection.commit()
    return bool(changed)


def add_playlist_item(
    user_connection: sqlite3.Connection,
    playlist_id: int,
    item_key: str,
    file_sha256: str | None,
) -> None:
    ensure_user_schema(user_connection)
    exists = user_connection.execute(
        "SELECT 1 FROM karaoke_playlists WHERE playlist_id=?", (playlist_id,)
    ).fetchone()
    if exists is None:
        raise ValueError("Unknown playlist")
    row = user_connection.execute(
        "SELECT COALESCE(MAX(position), -1)+1 AS position "
        "FROM karaoke_playlist_items WHERE playlist_id=?",
        (playlist_id,),
    ).fetchone()
    user_connection.execute(
        "INSERT OR IGNORE INTO karaoke_playlist_items"
        "(playlist_id, item_key, file_sha256, position) VALUES (?, ?, ?, ?)",
        (playlist_id, item_key, file_sha256, int(row["position"])),
    )
    user_connection.execute(
        "UPDATE karaoke_playlists SET updated_at=? WHERE playlist_id=?",
        (_now(), playlist_id),
    )
    user_connection.commit()


def remove_playlist_item(
    user_connection: sqlite3.Connection,
    playlist_id: int,
    item_key: str,
) -> dict[str, Any]:
    ensure_user_schema(user_connection)
    changed = user_connection.execute(
        "DELETE FROM karaoke_playlist_items "
        "WHERE playlist_id=? AND item_key=?",
        (playlist_id, item_key),
    ).rowcount
    if not changed:
        raise ValueError("Playlist item was not found")
    _normalize_playlist_positions(user_connection, playlist_id)
    user_connection.execute(
        "UPDATE karaoke_playlists SET updated_at=? WHERE playlist_id=?",
        (_now(), playlist_id),
    )
    user_connection.commit()
    return next(
        value
        for value in list_playlists(user_connection)
        if value["playlist_id"] == playlist_id
    )


def reorder_playlist_items(
    user_connection: sqlite3.Connection,
    playlist_id: int,
    item_keys: list[str],
) -> dict[str, Any]:
    ensure_user_schema(user_connection)
    rows = user_connection.execute(
        "SELECT item_key FROM karaoke_playlist_items "
        "WHERE playlist_id=? ORDER BY position",
        (playlist_id,),
    ).fetchall()
    existing = [str(row["item_key"]) for row in rows]
    if len(item_keys) != len(existing) or set(item_keys) != set(existing):
        raise ValueError("Reorder must contain every playlist item exactly once")
    # Offset first so the playlist's unique position index can never collide.
    user_connection.execute(
        "UPDATE karaoke_playlist_items SET position=position+1000000 "
        "WHERE playlist_id=?",
        (playlist_id,),
    )
    for position, item_key in enumerate(item_keys):
        user_connection.execute(
            "UPDATE karaoke_playlist_items SET position=? "
            "WHERE playlist_id=? AND item_key=?",
            (position, playlist_id, item_key),
        )
    user_connection.execute(
        "UPDATE karaoke_playlists SET updated_at=? WHERE playlist_id=?",
        (_now(), playlist_id),
    )
    user_connection.commit()
    return next(
        value
        for value in list_playlists(user_connection)
        if value["playlist_id"] == playlist_id
    )


def _normalize_playlist_positions(
    user_connection: sqlite3.Connection, playlist_id: int
) -> None:
    rows = user_connection.execute(
        "SELECT item_key FROM karaoke_playlist_items "
        "WHERE playlist_id=? ORDER BY position, added_at",
        (playlist_id,),
    ).fetchall()
    user_connection.execute(
        "UPDATE karaoke_playlist_items SET position=position+1000000 "
        "WHERE playlist_id=?",
        (playlist_id,),
    )
    for position, row in enumerate(rows):
        user_connection.execute(
            "UPDATE karaoke_playlist_items SET position=? "
            "WHERE playlist_id=? AND item_key=?",
            (position, playlist_id, row["item_key"]),
        )


def playback_state(
    user_connection: sqlite3.Connection, item_key: str
) -> dict[str, Any]:
    ensure_user_schema(user_connection)
    row = user_connection.execute(
        "SELECT * FROM karaoke_playback_state WHERE item_key=?", (item_key,)
    ).fetchone()
    return dict(row) if row is not None else {
        "item_key": item_key,
        "file_sha256": None,
        "position_seconds": 0,
        "duration_seconds": None,
        "completed": 0,
        "lyric_id": None,
        "lyric_offset_seconds": 0,
        "repeat_mode": "off",
        "shuffle": 0,
        "last_played_at": None,
        "play_count": 0,
    }


def save_playback_state(
    user_connection: sqlite3.Connection,
    item_key: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    ensure_user_schema(user_connection)
    repeat_mode = str(payload.get("repeat_mode", "off"))
    if repeat_mode not in {"off", "all", "one"}:
        raise ValueError("Invalid repeat mode")
    user_connection.execute(
        """INSERT INTO karaoke_playback_state
           (item_key, file_sha256, position_seconds, duration_seconds, completed,
            lyric_id, lyric_offset_seconds, repeat_mode, shuffle, last_played_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(item_key) DO UPDATE SET
             file_sha256=excluded.file_sha256,
             position_seconds=excluded.position_seconds,
             duration_seconds=excluded.duration_seconds,
             completed=excluded.completed, lyric_id=excluded.lyric_id,
             lyric_offset_seconds=excluded.lyric_offset_seconds,
             repeat_mode=excluded.repeat_mode, shuffle=excluded.shuffle,
             last_played_at=excluded.last_played_at""",
        (
            item_key,
            payload.get("file_sha256"),
            max(0.0, float(payload.get("position_seconds", 0))),
            payload.get("duration_seconds"),
            int(bool(payload.get("completed", False))),
            payload.get("lyric_id"),
            max(-30.0, min(30.0, float(payload.get("lyric_offset_seconds", 0)))),
            repeat_mode,
            int(bool(payload.get("shuffle", False))),
            _now(),
        ),
    )
    user_connection.commit()
    return playback_state(user_connection, item_key)


def record_play(
    user_connection: sqlite3.Connection,
    item_key: str,
    file_sha256: str | None,
) -> dict[str, Any]:
    ensure_user_schema(user_connection)
    user_connection.execute(
        """INSERT INTO karaoke_playback_state
           (item_key, file_sha256, last_played_at, play_count)
           VALUES (?, ?, ?, 1)
           ON CONFLICT(item_key) DO UPDATE SET
             file_sha256=excluded.file_sha256,
             last_played_at=excluded.last_played_at,
             play_count=karaoke_playback_state.play_count+1""",
        (item_key, file_sha256, _now()),
    )
    user_connection.commit()
    return playback_state(user_connection, item_key)
