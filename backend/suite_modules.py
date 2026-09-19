"""Persisted enablement state for the static suite module registry.

Tracks which optional modules the user has enabled. Files is an always-enabled
base descriptor and is never written here. "Enabled" is a user choice stored in the
shared, irreplaceable ``user.sqlite`` in the base/suite-owned
``suite_enabled_modules`` table (prefix convention). Isolated: no Danbooru or
``core`` imports. See docs/important/SUITE_MODULE_CONTRACT.md sections 3 and 6.

This state gates module visibility and module-owned background startup. Cheap
legacy schema initialization remains mounted for compatibility, so enabling a
module does not require restarting the suite; full physical Danbooru artifact
decoupling remains incremental work.
"""
from __future__ import annotations

import sqlite3

from config import MODULE_REGISTRY
from module_descriptor import ModuleDescriptor


SUITE_MODULES_SCHEMA = """
CREATE TABLE IF NOT EXISTS suite_enabled_modules (
    module TEXT PRIMARY KEY,
    enabled_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS suite_module_migrations (
    key TEXT PRIMARY KEY,
    completed_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

def ensure_schema(user_conn: sqlite3.Connection) -> None:
    """Create the enabled-modules table if absent (idempotent, additive)."""
    user_conn.executescript(SUITE_MODULES_SCHEMA)
    user_conn.commit()


def enable_existing_modules_once(user_conn: sqlite3.Connection) -> list[str]:
    """Preserve pre-registry installations without changing later choices.

    Only the first registry-aware launch inspects existing module databases.
    The marker makes an intentionally disabled module stay disabled forever
    after that launch.
    """
    ensure_schema(user_conn)
    migration_key = "existing_modules_enabled_v1"
    if user_conn.execute(
        "SELECT 1 FROM suite_module_migrations WHERE key=?", (migration_key,)
    ).fetchone():
        return []
    enabled: list[str] = []
    for descriptor in MODULE_REGISTRY.optional():
        if descriptor.database.is_file() or (descriptor.home / "user.sqlite").is_file():
            user_conn.execute(
                "INSERT OR IGNORE INTO suite_enabled_modules(module) VALUES (?)",
                (descriptor.slug,),
            )
            enabled.append(descriptor.slug)
    user_conn.execute(
        "INSERT INTO suite_module_migrations(key) VALUES (?)", (migration_key,)
    )
    user_conn.commit()
    return enabled


def descriptors() -> tuple[ModuleDescriptor, ...]:
    return tuple(MODULE_REGISTRY)


def is_known(module_id: str) -> bool:
    return MODULE_REGISTRY.get(module_id) is not None


def enabled_ids(user_conn: sqlite3.Connection) -> set[str]:
    rows = user_conn.execute("SELECT module FROM suite_enabled_modules").fetchall()
    return {row["module"] for row in rows}


def set_enabled(user_conn: sqlite3.Connection, module_id: str, enabled: bool) -> None:
    descriptor = MODULE_REGISTRY.require(module_id)
    if not descriptor.disableable:
        if not enabled:
            raise ValueError(f"{descriptor.name} is the required suite base")
        return
    if enabled:
        user_conn.execute(
            "INSERT OR IGNORE INTO suite_enabled_modules (module) VALUES (?)",
            (module_id,),
        )
    else:
        user_conn.execute(
            "DELETE FROM suite_enabled_modules WHERE module = ?", (module_id,)
        )
    user_conn.commit()
