"""Descriptor and Files publication hook for the Manayomi manga module.

The public module identity is ``manayomi`` while its existing writable home
remains ``modules/manga``. Keeping that historical storage location preserves
every current index and user record without a second database migration.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from files_base import sources
from module_descriptor import ModuleDescriptor


def publish_sources(user_connection: sqlite3.Connection) -> None:
    """Project existing Manayomi roots into the neutral Files base."""
    from manga.roots import list_roots

    sources.ensure_sources_schema(user_connection)
    folders = [
        (str(root["path"]), root.get("label") or Path(str(root["path"])).name)
        for root in list_roots()
        if Path(str(root["path"])).is_dir()
    ]
    sources.reconcile_module_sources(user_connection, "manayomi", folders)


def descriptor(suite_home: Path, version: str) -> ModuleDescriptor:
    home = suite_home / "modules" / "manga"
    return ModuleDescriptor(
        slug="manayomi",
        name="Manayomi",
        home=home,
        database=home / "manga.sqlite",
        credentials=None,
        api_prefix="/api/manga",
        log_prefix="manayomi",
        user_agent=f"Keivotos/{version} (Manayomi local manga library)",
        disableable=True,
        is_base=False,
        publish_hook=publish_sources,
    )
