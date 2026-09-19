"""Registered manga library roots. Files are indexed in place, never moved.

Roots live in the module user database; removing a root only un-indexes its
manga rows — originals on disk are never touched.
"""
from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

from manga.database import index_session, user_session
from manga.paths import MANGA_USER_DB_PATH
from storage_layout import relative_path_for_relocation


class RootRelocationError(ValueError):
    """A root path cannot be changed without invalidating indexed files."""


def _resolved_directory(input_path: str) -> Path:
    cleaned = (input_path or "").strip()
    if not cleaned:
        raise RootRelocationError("Empty destination path")
    path = Path(cleaned).expanduser()
    if not path.exists():
        raise RootRelocationError("Destination folder does not exist")
    if not path.is_dir():
        raise RootRelocationError("Destination is not a folder")
    return path.resolve(strict=True)


def _relative_to_root(file_path: str, root_path: str) -> Path:
    try:
        relative = relative_path_for_relocation(file_path, root_path)
    except ValueError as exc:
        raise RootRelocationError(f"Indexed path is outside the old root: {file_path}") from exc
    if relative.is_absolute() or not relative.parts or relative.parts[0] == "..":
        raise RootRelocationError(f"Indexed path is outside the old root: {file_path}")
    return relative


def _relocation_plan(root_id: int, input_path: str) -> tuple[dict[str, Any], list[tuple[str, int]]]:
    root = get_root(root_id)
    if root is None:
        raise RootRelocationError("Unknown manga root")
    old_root = str(root["path"])
    new_root = _resolved_directory(input_path)
    if os.path.normcase(str(old_root)) == os.path.normcase(str(new_root)):
        with index_session() as index:
            count = index.execute(
                "SELECT COUNT(*) FROM manga WHERE root_id=?", (root_id,)
            ).fetchone()[0]
        return ({
            "root_id": root_id,
            "old_path": str(old_root),
            "new_path": str(new_root),
            "indexed_files": count,
            "verified_files": count,
            "missing_files": 0,
            "unchanged": True,
        }, [])
    conflict = get_root_by_path(str(new_root))
    if conflict is not None and int(conflict["id"]) != root_id:
        raise RootRelocationError("Destination is already registered as another manga root")

    mappings: list[tuple[str, int]] = []
    missing: list[str] = []
    with index_session() as index:
        rows = index.execute(
            "SELECT id, file_path FROM manga WHERE root_id=? ORDER BY id", (root_id,)
        ).fetchall()
        other_paths = {
            os.path.normcase(str(row[0]))
            for row in index.execute("SELECT file_path FROM manga WHERE root_id<>?", (root_id,))
        }
    for row in rows:
        relative = _relative_to_root(str(row["file_path"]), old_root)
        destination = (new_root / relative).resolve(strict=False)
        if new_root != destination and new_root not in destination.parents:
            raise RootRelocationError(f"Relocated path escapes the destination root: {relative}")
        if os.path.normcase(str(destination)) in other_paths:
            raise RootRelocationError(f"Relocated path conflicts with another indexed manga: {destination}")
        if not destination.is_file():
            missing.append(str(destination))
        mappings.append((str(destination), int(row["id"])))
    if missing:
        example = missing[0]
        raise RootRelocationError(
            f"Destination is missing {len(missing)} of {len(mappings)} indexed files; first missing: {example}"
        )
    return ({
        "root_id": root_id,
        "old_path": str(old_root),
        "new_path": str(new_root),
        "indexed_files": len(mappings),
        "verified_files": len(mappings),
        "missing_files": 0,
        "unchanged": False,
    }, mappings)


def preview_relocation(root_id: int, input_path: str) -> dict[str, Any]:
    """Verify every new indexed path without changing either database."""
    preview, _ = _relocation_plan(root_id, input_path)
    return preview


def relocate_root(root_id: int, input_path: str) -> dict[str, Any]:
    """Atomically rebase index paths and the registered root; move no files."""
    preview, mappings = _relocation_plan(root_id, input_path)
    if preview["unchanged"]:
        return preview
    root = get_root(root_id)
    if root is None:
        raise RootRelocationError("Unknown manga root")
    old_name = Path(str(root["path"])).name
    label = root.get("label")
    if not label or label == old_name:
        label = Path(str(preview["new_path"])).name
    with index_session() as index:
        index.execute("ATTACH DATABASE ? AS mangauser", (str(MANGA_USER_DB_PATH),))
        index.executemany("UPDATE manga SET file_path=? WHERE id=?", mappings)
        index.execute(
            "UPDATE mangauser.roots SET path=?, label=? WHERE id=?",
            (preview["new_path"], label, root_id),
        )
        expected_paths = {manga_id: os.path.normcase(path) for path, manga_id in mappings}
        updated_rows = index.execute(
            "SELECT id, file_path FROM manga WHERE root_id=?", (root_id,)
        ).fetchall()
        changed = sum(
            expected_paths.get(int(row["id"])) == os.path.normcase(str(row["file_path"]))
            for row in updated_rows
        )
        if changed != len(mappings) or len(updated_rows) != len(mappings):
            raise RootRelocationError(
                f"Relocation verification failed: updated {changed} of {len(mappings)} index rows"
            )
    return preview


def list_roots() -> list[dict[str, Any]]:
    with user_session() as user:
        rows = [dict(row) for row in user.execute("SELECT * FROM roots ORDER BY added_at ASC")]
    with index_session() as index:
        for root in rows:
            count = index.execute(
                "SELECT COUNT(*) FROM manga WHERE root_id = ?", (root["id"],)
            ).fetchone()[0]
            root["manga_count"] = count
    return rows


def get_root(root_id: int) -> dict[str, Any] | None:
    with user_session() as user:
        row = user.execute("SELECT * FROM roots WHERE id = ?", (root_id,)).fetchone()
    return dict(row) if row is not None else None


def get_root_by_path(path: str) -> dict[str, Any] | None:
    resolved = str(Path(path).expanduser().resolve(strict=False))
    with user_session() as user:
        row = user.execute("SELECT * FROM roots WHERE path = ?", (resolved,)).fetchone()
    return dict(row) if row is not None else None


def add_root(input_path: str) -> dict[str, Any]:
    """Register an existing folder. Returns {ok, root?/error?}."""
    cleaned = (input_path or "").strip()
    if not cleaned:
        return {"ok": False, "error": "Empty path"}
    path = Path(cleaned).expanduser()
    if not path.exists():
        return {"ok": False, "error": "Folder does not exist"}
    if not path.is_dir():
        return {"ok": False, "error": "Not a folder"}
    resolved = str(path.resolve(strict=False))

    existing = get_root_by_path(resolved)
    if existing is not None:
        return {"ok": True, "root": existing}
    with user_session() as user:
        cursor = user.execute(
            "INSERT INTO roots (path, label, added_at) VALUES (?, ?, ?)",
            (resolved, path.name, int(time.time() * 1000)),
        )
        row_id = cursor.lastrowid
    return {"ok": True, "root": get_root(int(row_id))}


def ensure_default_root() -> dict[str, Any] | None:
    """Compatibility no-op: roots are user-registered, never hard-coded."""
    return None


def download_root() -> dict[str, Any] | None:
    """Use the first currently available registered root for new downloads."""
    roots = list_roots()
    return next((root for root in roots if Path(str(root["path"])).is_dir()), None)


def mark_scanned(root_id: int) -> None:
    with user_session() as user:
        user.execute(
            "UPDATE roots SET last_scan_at = ? WHERE id = ?",
            (int(time.time() * 1000), root_id),
        )


def remove_root(root_id: int) -> None:
    """Forget a root and its indexed manga. Never touches files on disk."""
    with index_session() as index:
        manga_ids = [row[0] for row in index.execute("SELECT id FROM manga WHERE root_id = ?", (root_id,))]
        for manga_id in manga_ids:
            tag_ids = [row[0] for row in index.execute(
                "SELECT tag_id FROM manga_tags WHERE manga_id = ?", (manga_id,)
            )]
            index.execute("DELETE FROM manga_tags WHERE manga_id = ?", (manga_id,))
            for tag_id in tag_ids:
                index.execute("UPDATE tags SET manga_count = manga_count - 1 WHERE id = ?", (tag_id,))
        index.execute("DELETE FROM manga WHERE root_id = ?", (root_id,))
        index.execute("DELETE FROM tags WHERE manga_count <= 0")
    with user_session() as user:
        user.execute("DELETE FROM roots WHERE id = ?", (root_id,))
