"""Contained, create-only storage helpers for YouTube acquisitions."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any


SAFE_NAME_RE = re.compile(r"[^\w .,'()\-\[\]]+", re.UNICODE)
VIDEO_SUFFIXES = {".m4v", ".mkv", ".mov", ".mp4", ".webm"}
AUDIO_SUFFIXES = {".aac", ".flac", ".m4a", ".mp3", ".ogg", ".opus", ".wav"}
SUBTITLE_SUFFIXES = {".ass", ".ssa", ".srt", ".vtt", ".lrc"}
IMAGE_SUFFIXES = {".avif", ".jpeg", ".jpg", ".png", ".webp"}


class YouTubeStorageError(RuntimeError):
    pass


def ensure_layout(home: Path) -> dict[str, Path]:
    values = {
        "home": home,
        "library": home / "media" / "library",
        "staging": home / "staging",
        "thumbnail_cache": home / "cache" / "search-thumbnails",
    }
    for path in values.values():
        path.mkdir(parents=True, exist_ok=True)
    return values


def safe_name(value: str, fallback: str, limit: int = 100) -> str:
    clean = SAFE_NAME_RE.sub(" ", value).strip().rstrip(". ")
    clean = re.sub(r"\s+", " ", clean)
    return (clean or fallback)[:limit].rstrip(". ")


def item_directory_name(video_id: str, title: str) -> str:
    return f"{safe_name(video_id, 'youtube', 32)} - {safe_name(title, 'Untitled')}"


def resolve_within(root: Path, relative: str, *, require_file: bool = False) -> Path:
    root = root.expanduser().resolve(strict=False)
    try:
        candidate = (root / relative.replace("\\", "/")).resolve(strict=require_file)
        candidate.relative_to(root)
    except (OSError, ValueError) as exc:
        raise YouTubeStorageError("Local YouTube path is unavailable") from exc
    if require_file and not candidate.is_file():
        raise YouTubeStorageError("Local YouTube file is unavailable")
    return candidate


def hash_file(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    total = 0
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
            total += len(chunk)
    return digest.hexdigest(), total


def write_json_create(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".writing")
    if path.exists() or temporary.exists():
        raise YouTubeStorageError(f"Refusing to replace existing file: {path}")
    try:
        with temporary.open("xb") as handle:
            handle.write(
                json.dumps(
                    payload,
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                ).encode("utf-8")
            )
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except Exception:
        if temporary.exists():
            temporary.unlink()
        raise


def publish_staged_directory(stage: Path, destination: Path) -> None:
    if destination.exists():
        raise YouTubeStorageError(
            f"YouTube library variant already exists: {destination.name}"
        )
    destination.parent.mkdir(parents=True, exist_ok=True)
    os.replace(stage, destination)
