"""Descriptor and suite hooks for the optional Languages module."""
from __future__ import annotations

import sqlite3
from functools import partial
from pathlib import Path
from typing import Any

from files_base import sources
from module_descriptor import ModuleDescriptor
from modules.language import catalog, storage, user_state


def publish_sources(
    user_connection: sqlite3.Connection,
    *,
    home: Path,
    database: Path,
    library_root: Path,
) -> None:
    """Initialize enabled storage and publish it without dropping study folders."""
    storage.ensure_layout(home)
    with catalog.open_catalog(database):
        pass
    user_state.ensure_user_schema(user_connection)
    sources.ensure_sources_schema(user_connection)

    library_source_id = sources.deterministic_source_id(library_root)
    folders = [
        (source.path, source.display_name)
        for source in sources.list_sources(user_connection)
        if sources.canonical_role(source.role) == "language"
        and source.source_id != library_source_id
    ]
    folders.append((str(library_root), "Languages media"))
    sources.reconcile_module_sources(user_connection, "language", folders)


def adopt_source(source_id: str) -> dict[str, Any]:
    """Assign an existing Files source to Languages without touching disk."""
    from database import get_user_db

    with get_user_db() as connection:
        sources.ensure_sources_schema(connection)
        if sources.get_source(connection, source_id) is None:
            raise ValueError("Unknown Files source")
        sources.update_source(connection, source_id, role="language")
    return {
        "source_id": source_id,
        "status": "adopted",
        "module_files": 0,
        "sidecars_preserved": 0,
    }


def release_source(source_id: str, forget: bool = False) -> dict[str, Any]:
    """Release registry ownership while preserving every file on disk."""
    from database import get_user_db

    with get_user_db() as connection:
        sources.ensure_sources_schema(connection)
        if sources.get_source(connection, source_id) is None:
            raise ValueError("Unknown Files source")
        if forget:
            sources.remove_source(connection, source_id)
        else:
            sources.update_source(connection, source_id, role="files")
    return {
        "source_id": source_id,
        "status": "forgotten" if forget else "released",
        "module_files": 0,
        "sidecars_preserved": 0,
    }


def folder_preview(source_id: str) -> dict[str, Any]:
    """Languages never adds private rows or sidecars for assigned study folders."""
    return {
        "source_id": source_id,
        "module_files": 0,
        "sidecars_preserved": 0,
    }


def descriptor(suite_home: Path, version: str) -> ModuleDescriptor:
    home = suite_home / "modules" / "language"
    database = home / "language.sqlite"
    library_root = home / "media" / "library"
    return ModuleDescriptor(
        slug="language",
        name="Languages",
        home=home,
        database=database,
        credentials=home / "language_credentials.json",
        api_prefix="/api/language",
        log_prefix="language",
        user_agent=f"Keivotos/{version} (Languages local study library)",
        disableable=True,
        is_base=False,
        browsable_roots=(library_root,),
        publish_hook=partial(
            publish_sources,
            home=home,
            database=database,
            library_root=library_root,
        ),
        adopt_hook=adopt_source,
        release_hook=release_source,
        folder_preview_hook=folder_preview,
    )
