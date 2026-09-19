"""Descriptor and suite hooks for the optional local YouTube module."""
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
    sources.ensure_sources_schema(user_connection)
    folders = (
        [(str(library_root), "YouTube downloads")]
        if library_root.is_dir()
        else []
    )
    sources.reconcile_module_sources(user_connection, "youtube", folders)


def descriptor(suite_home: Path, version: str) -> ModuleDescriptor:
    home = suite_home / "modules" / "youtube"
    library_root = home / "media" / "library"
    return ModuleDescriptor(
        slug="youtube",
        name="YouTube",
        home=home,
        database=home / "youtube.sqlite",
        credentials=None,
        api_prefix="/api/youtube",
        log_prefix="youtube",
        user_agent=f"Keivotos/{version} (YouTube local acquisition)",
        disableable=True,
        is_base=False,
        browsable_roots=(library_root,),
        publish_hook=partial(publish_sources, library_root=library_root),
    )
