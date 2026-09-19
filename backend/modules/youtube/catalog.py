"""Rebuildable YouTube library, plans, and download jobs."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Any, Generator


SCHEMA = """
CREATE TABLE IF NOT EXISTS youtube_items (
    item_id TEXT PRIMARY KEY,
    video_id TEXT NOT NULL,
    title TEXT NOT NULL,
    channel TEXT NOT NULL DEFAULT '',
    duration REAL,
    upload_date TEXT,
    view_count INTEGER,
    quality_label TEXT NOT NULL,
    video_path TEXT NOT NULL,
    video_sha256 TEXT NOT NULL,
    thumbnail_path TEXT,
    audio_paths_json TEXT NOT NULL DEFAULT '[]',
    subtitles_json TEXT NOT NULL DEFAULT '[]',
    metadata_path TEXT NOT NULL,
    receipt_path TEXT NOT NULL,
    metadata_json TEXT NOT NULL,
    karaoke_intent INTEGER NOT NULL DEFAULT 0,
    added_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(video_id, quality_label)
);
CREATE INDEX IF NOT EXISTS idx_youtube_items_title
    ON youtube_items(title COLLATE NOCASE);

CREATE TABLE IF NOT EXISTS youtube_plans (
    token TEXT PRIMARY KEY,
    video_id TEXT NOT NULL,
    selection_sha256 TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    expires_at TEXT NOT NULL,
    consumed_at TEXT
);

CREATE TABLE IF NOT EXISTS youtube_jobs (
    job_id TEXT PRIMARY KEY,
    plan_token TEXT NOT NULL,
    video_id TEXT NOT NULL,
    status TEXT NOT NULL,
    phase TEXT NOT NULL,
    progress REAL NOT NULL DEFAULT 0,
    downloaded_bytes INTEGER NOT NULL DEFAULT 0,
    total_bytes INTEGER,
    speed REAL,
    eta REAL,
    error TEXT,
    item_id TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS youtube_playback_state (
    item_id TEXT PRIMARY KEY,
    position_seconds REAL NOT NULL DEFAULT 0,
    duration_seconds REAL,
    completed INTEGER NOT NULL DEFAULT 0,
    last_played_at TEXT,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _loads(value: str | None, fallback: Any) -> Any:
    try:
        return json.loads(value) if value else fallback
    except (TypeError, ValueError):
        return fallback


@contextmanager
def open_catalog(path: Path) -> Generator[sqlite3.Connection, None, None]:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.executescript(SCHEMA)
        connection.commit()
        yield connection
    finally:
        connection.close()


def recover_interrupted_jobs(connection: sqlite3.Connection) -> int:
    changed = connection.execute(
        "UPDATE youtube_jobs SET status='interrupted', phase='interrupted', "
        "updated_at=? WHERE status IN ('queued', 'running')",
        (_now(),),
    ).rowcount
    connection.commit()
    return max(changed, 0)


def item_from_row(row: sqlite3.Row) -> dict[str, Any]:
    value = dict(row)
    value["audio_paths"] = _loads(value.pop("audio_paths_json"), [])
    value["subtitles"] = _loads(value.pop("subtitles_json"), [])
    value["metadata"] = _loads(value.pop("metadata_json"), {})
    value["karaoke_intent"] = bool(value["karaoke_intent"])
    return value


def list_items(
    connection: sqlite3.Connection,
    *,
    query: str = "",
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    pattern = f"%{query.strip()}%"
    rows = connection.execute(
        "SELECT * FROM youtube_items "
        "WHERE (?='' OR title LIKE ? COLLATE NOCASE OR channel LIKE ? COLLATE NOCASE) "
        "ORDER BY added_at DESC, title COLLATE NOCASE LIMIT ? OFFSET ?",
        (query.strip(), pattern, pattern, limit, offset),
    ).fetchall()
    return [item_from_row(row) for row in rows]


def get_item(connection: sqlite3.Connection, item_id: str) -> dict[str, Any] | None:
    row = connection.execute(
        "SELECT * FROM youtube_items WHERE item_id=?", (item_id,)
    ).fetchone()
    return item_from_row(row) if row is not None else None


def insert_item(connection: sqlite3.Connection, item: dict[str, Any]) -> None:
    connection.execute(
        """INSERT INTO youtube_items
           (item_id, video_id, title, channel, duration, upload_date, view_count,
            quality_label, video_path, video_sha256, thumbnail_path,
            audio_paths_json, subtitles_json, metadata_path, receipt_path,
            metadata_json, karaoke_intent)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            item["item_id"],
            item["video_id"],
            item["title"],
            item.get("channel", ""),
            item.get("duration"),
            item.get("upload_date"),
            item.get("view_count"),
            item["quality_label"],
            item["video_path"],
            item["video_sha256"],
            item.get("thumbnail_path"),
            json.dumps(item.get("audio_paths", []), ensure_ascii=False),
            json.dumps(item.get("subtitles", []), ensure_ascii=False),
            item["metadata_path"],
            item["receipt_path"],
            json.dumps(item.get("metadata", {}), ensure_ascii=False, sort_keys=True),
            int(bool(item.get("karaoke_intent", False))),
        ),
    )
    connection.commit()


def update_item(connection: sqlite3.Connection, item: dict[str, Any]) -> None:
    connection.execute(
        """UPDATE youtube_items
           SET video_id=?, title=?, channel=?, duration=?, upload_date=?,
               view_count=?, quality_label=?, video_path=?, video_sha256=?,
               thumbnail_path=?, audio_paths_json=?, subtitles_json=?,
               metadata_path=?, receipt_path=?, metadata_json=?,
               karaoke_intent=?
           WHERE item_id=?""",
        (
            item["video_id"],
            item["title"],
            item.get("channel", ""),
            item.get("duration"),
            item.get("upload_date"),
            item.get("view_count"),
            item["quality_label"],
            item["video_path"],
            item["video_sha256"],
            item.get("thumbnail_path"),
            json.dumps(item.get("audio_paths", []), ensure_ascii=False),
            json.dumps(item.get("subtitles", []), ensure_ascii=False),
            item["metadata_path"],
            item["receipt_path"],
            json.dumps(item.get("metadata", {}), ensure_ascii=False, sort_keys=True),
            int(bool(item.get("karaoke_intent", False))),
            item["item_id"],
        ),
    )
    connection.commit()


def store_plan(
    connection: sqlite3.Connection,
    *,
    token: str,
    video_id: str,
    selection_sha256: str,
    payload: dict[str, Any],
    expires_at: str,
) -> None:
    connection.execute(
        "INSERT INTO youtube_plans"
        "(token, video_id, selection_sha256, payload_json, expires_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (
            token,
            video_id,
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
        "SELECT * FROM youtube_plans WHERE token=?", (token,)
    ).fetchone()
    if row is None or (row["consumed_at"] and not allow_consumed):
        return None
    value = dict(row)
    value["payload"] = _loads(value.pop("payload_json"), {})
    return value


def consume_plan(connection: sqlite3.Connection, token: str) -> bool:
    changed = connection.execute(
        "UPDATE youtube_plans SET consumed_at=? "
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
    video_id: str,
) -> dict[str, Any]:
    connection.execute(
        "INSERT INTO youtube_jobs"
        "(job_id, plan_token, video_id, status, phase) "
        "VALUES (?, ?, ?, 'queued', 'queued')",
        (job_id, plan_token, video_id),
    )
    connection.commit()
    value = get_job(connection, job_id)
    assert value is not None
    return value


def update_job(
    connection: sqlite3.Connection,
    job_id: str,
    **values: Any,
) -> dict[str, Any]:
    allowed = {
        "status",
        "phase",
        "progress",
        "downloaded_bytes",
        "total_bytes",
        "speed",
        "eta",
        "error",
        "item_id",
    }
    assignments = ["updated_at=?"]
    parameters: list[Any] = [_now()]
    for name, value in values.items():
        if name in allowed and value is not None:
            assignments.append(f"{name}=?")
            parameters.append(value)
    parameters.append(job_id)
    connection.execute(
        f"UPDATE youtube_jobs SET {', '.join(assignments)} WHERE job_id=?",
        parameters,
    )
    connection.commit()
    item = get_job(connection, job_id)
    if item is None:
        raise ValueError("Unknown YouTube job")
    return item


def get_job(connection: sqlite3.Connection, job_id: str) -> dict[str, Any] | None:
    row = connection.execute(
        "SELECT * FROM youtube_jobs WHERE job_id=?", (job_id,)
    ).fetchone()
    return dict(row) if row is not None else None


def list_jobs(connection: sqlite3.Connection, limit: int = 25) -> list[dict[str, Any]]:
    return [
        dict(row)
        for row in connection.execute(
            "SELECT * FROM youtube_jobs ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    ]


def playback_state(
    connection: sqlite3.Connection, item_id: str
) -> dict[str, Any]:
    row = connection.execute(
        "SELECT * FROM youtube_playback_state WHERE item_id=?", (item_id,)
    ).fetchone()
    return dict(row) if row is not None else {
        "item_id": item_id,
        "position_seconds": 0,
        "duration_seconds": None,
        "completed": 0,
        "last_played_at": None,
        "updated_at": None,
    }


def save_playback_state(
    connection: sqlite3.Connection,
    item_id: str,
    *,
    position_seconds: float,
    duration_seconds: float | None,
    completed: bool,
) -> dict[str, Any]:
    if get_item(connection, item_id) is None:
        raise ValueError("Unknown YouTube item")
    now = _now()
    connection.execute(
        """INSERT INTO youtube_playback_state
           (item_id, position_seconds, duration_seconds, completed,
            last_played_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?)
           ON CONFLICT(item_id) DO UPDATE SET
             position_seconds=excluded.position_seconds,
             duration_seconds=excluded.duration_seconds,
             completed=excluded.completed,
             last_played_at=excluded.last_played_at,
             updated_at=excluded.updated_at""",
        (
            item_id,
            max(0.0, float(position_seconds)),
            duration_seconds,
            int(bool(completed)),
            now,
            now,
        ),
    )
    connection.commit()
    return playback_state(connection, item_id)
