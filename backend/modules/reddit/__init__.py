"""Descriptor for the optional local-first Reddit module."""
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
    """Publish the friendly Reddit download tree into the Files base."""
    sources.ensure_sources_schema(user_connection)
    folders = (
        [(str(library_root), "Reddit downloads")]
        if library_root.is_dir()
        else []
    )
    sources.reconcile_module_sources(user_connection, "reddit", folders)


def descriptor(suite_home: Path, version: str) -> ModuleDescriptor:
    home = suite_home / "modules" / "reddit"
    library_root = home / "media" / "library"
    return ModuleDescriptor(
        slug="reddit",
        name="Reddit",
        home=home,
        database=home / "reddit.sqlite",
        credentials=None,
        api_prefix="/api/reddit",
        log_prefix="reddit",
        user_agent=f"Keivotos/{version} (Reddit local archive)",
        disableable=True,
        is_base=False,
        browsable_roots=(library_root,),
        publish_hook=partial(publish_sources, library_root=library_root),
    )
