"""Automatic snapshots of the manga user database (port of backup.ts).

``VACUUM INTO`` a timestamped copy after each scan/download and on startup;
the newest five are kept. Only the irreplaceable user DB is snapshotted — the
index DB is rebuildable from sidecars.
"""
from __future__ import annotations

import logging
import sqlite3
import time
from datetime import datetime

from manga.paths import MANGA_BACKUP_DIR, MANGA_USER_DB_PATH

logger = logging.getLogger("keivotos")

KEEP = 5
MIN_INTERVAL_SECONDS = 60
_last_backup_at = 0.0


def maybe_backup(reason: str) -> None:
    """Snapshot the user DB unless one was taken moments ago."""
    global _last_backup_at
    if time.monotonic() - _last_backup_at < MIN_INTERVAL_SECONDS:
        return
    if not MANGA_USER_DB_PATH.is_file():
        return
    try:
        MANGA_BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        target = MANGA_BACKUP_DIR / f"user-{stamp}.sqlite"
        if target.exists():
            return
        connection = sqlite3.connect(MANGA_USER_DB_PATH)
        try:
            connection.execute("VACUUM INTO ?", (str(target),))
        finally:
            connection.close()
        _last_backup_at = time.monotonic()
        logger.info("manga user-DB backup (%s): %s", reason, target.name)
        _prune()
    except Exception as exc:  # noqa: BLE001 - backups must never break the caller
        logger.error("manga backup failed (%s): %s", reason, exc)


def _prune() -> None:
    snapshots = sorted(
        MANGA_BACKUP_DIR.glob("user-*.sqlite"),
        key=lambda path: path.name,
        reverse=True,
    )
    for stale in snapshots[KEEP:]:
        try:
            stale.unlink()
        except OSError:
            pass
