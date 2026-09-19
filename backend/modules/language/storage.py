"""Contained, create-only storage helpers for Languages media."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
from typing import Any
import uuid


SAFE_NAME_RE = re.compile(r'[<>:"/\\|?*\x00-\x1f]+')


class LanguageStorageError(RuntimeError):
    pass


def ensure_layout(home: Path) -> dict[str, Path]:
    values = {
        "home": home,
        "library": home / "media" / "library",
        "staging": home / "staging",
    }
    for path in values.values():
        path.mkdir(parents=True, exist_ok=True)
    return values


def resolve_within(root: Path, relative: str, *, require_file: bool = False) -> Path:
    root = root.expanduser().resolve(strict=False)
    try:
        candidate = (root / relative.replace("\\", "/")).resolve(strict=require_file)
        candidate.relative_to(root)
    except (OSError, ValueError) as exc:
        raise LanguageStorageError("Local Languages path is unavailable") from exc
    if require_file and not candidate.is_file():
        raise LanguageStorageError("Local Languages file is unavailable")
    return candidate


def safe_word_key(headword: str, fallback: str = "word", limit: int = 100) -> str:
    clean = SAFE_NAME_RE.sub(" ", headword).strip().rstrip(". ")
    clean = re.sub(r"\s+", " ", clean)
    return (clean or fallback)[:limit].rstrip(". ")


def versioned_media_name(role: str, sha256: str, origin_filename: str) -> str:
    clean_role = safe_word_key(role, "media", 40).replace(" ", "-")
    suffix = Path(origin_filename).suffix.casefold()
    if not suffix or len(suffix) > 12 or not suffix[1:].isalnum():
        suffix = ".bin"
    return f"{clean_role}.{sha256[:12]}{suffix}"


def metadata_receipt_name(sync_id: str) -> str:
    clean_sync_id = safe_word_key(sync_id, "sync", 60).replace(" ", "-")
    return f"note.{clean_sync_id}.metadata.json"


def hash_file(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    total = 0
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
            total += len(chunk)
    return digest.hexdigest(), total


def _install_staged_file(stage: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise LanguageStorageError(f"Refusing to replace existing file: {destination}")
    try:
        os.link(stage, destination)
    except FileExistsError as exc:
        raise LanguageStorageError(
            f"Refusing to replace existing file: {destination}"
        ) from exc
    finally:
        if stage.exists():
            stage.unlink()


def copy_file_create(source: Path, destination: Path) -> tuple[str, int]:
    if not source.is_file():
        raise LanguageStorageError("Source file is unavailable")
    destination.parent.mkdir(parents=True, exist_ok=True)
    stage = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.staging")
    try:
        with source.open("rb") as source_handle, stage.open("xb") as stage_handle:
            shutil.copyfileobj(source_handle, stage_handle, 1024 * 1024)
            stage_handle.flush()
            os.fsync(stage_handle.fileno())
        digest, total = hash_file(stage)
        _install_staged_file(stage, destination)
        return digest, total
    except Exception:
        if stage.exists():
            stage.unlink()
        raise


def write_json_create(path: Path, payload: Any) -> tuple[str, int]:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ).encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    stage = path.with_name(f".{path.name}.{uuid.uuid4().hex}.staging")
    try:
        with stage.open("xb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        _install_staged_file(stage, path)
    except Exception:
        if stage.exists():
            stage.unlink()
        raise
    return hashlib.sha256(encoded).hexdigest(), len(encoded)


def write_bytes_create(path: Path, payload: bytes) -> tuple[str, int]:
    """Install immutable bytes without ever replacing an existing artifact."""
    path.parent.mkdir(parents=True, exist_ok=True)
    stage = path.with_name(f".{path.name}.{uuid.uuid4().hex}.staging")
    try:
        with stage.open("xb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        _install_staged_file(stage, path)
    except Exception:
        if stage.exists():
            stage.unlink()
        raise
    return hashlib.sha256(payload).hexdigest(), len(payload)
