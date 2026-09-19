"""Descriptor and suite hooks for the optional local Karaoke module."""
from __future__ import annotations

import sqlite3
from functools import partial
from pathlib import Path

from files_base import sources
from module_descriptor import ModuleDescriptor


def publish_sources(
    user_connection: sqlite3.Connection,
    *,
    library_root: Path,
) -> None:
    """Publish the module-owned local library into the Files base."""
    sources.ensure_sources_schema(user_connection)
    folders = (
        [(str(library_root), "Karaoke library")]
        if library_root.is_dir()
        else []
    )
    sources.reconcile_module_sources(user_connection, "karaoke", folders)


def descriptor(suite_home: Path, version: str) -> ModuleDescriptor:
    home = suite_home / "modules" / "karaoke"
    library_root = home / "media" / "library"
    return ModuleDescriptor(
        slug="karaoke",
        name="Karaoke",
        home=home,
        database=home / "karaoke.sqlite",
        credentials=None,
        api_prefix="/api/karaoke",
        log_prefix="karaoke",
        user_agent=f"Keivotos/{version} (Karaoke local library)",
        disableable=True,
        is_base=False,
        browsable_roots=(library_root,),
        publish_hook=partial(publish_sources, library_root=library_root),
    )
