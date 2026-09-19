"""Contained, create-only storage primitives for local karaoke artifacts."""
from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import struct
from typing import Any

from thumbnails import resolve_ffmpeg_executable


SAFE_NAME_RE = re.compile(r"[^\w .,'()\-\[\]]+", re.UNICODE)
SAFE_SUBTITLE_SUFFIXES = {".ass", ".ssa", ".srt", ".vtt", ".lrc"}
SAFE_MEDIA_SUFFIXES = {
    ".aac",
    ".flac",
    ".m4a",
    ".m4v",
    ".mkv",
    ".mp3",
    ".mp4",
    ".ogg",
    ".opus",
    ".wav",
    ".webm",
}


class KaraokeStorageError(RuntimeError):
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


def safe_name(value: str, fallback: str, limit: int = 96) -> str:
    clean = SAFE_NAME_RE.sub(" ", value).strip().rstrip(". ")
    clean = re.sub(r"\s+", " ", clean)
    return (clean or fallback)[:limit].rstrip(". ")


def item_directory_name(provider_id: str, title: str) -> str:
    return f"{safe_name(provider_id, 'karaoke', 48)} - {safe_name(title, 'Untitled')}"


def resolve_within(root: Path, relative: str, *, require_file: bool = False) -> Path:
    root = root.expanduser().resolve(strict=False)
    try:
        candidate = (root / relative.replace("\\", "/")).resolve(strict=require_file)
        candidate.relative_to(root)
    except (OSError, ValueError) as exc:
        raise KaraokeStorageError("Local karaoke path is unavailable") from exc
    if require_file and not candidate.is_file():
        raise KaraokeStorageError("Local karaoke file is unavailable")
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
        raise KaraokeStorageError(f"Refusing to replace existing file: {path}")
    data = json.dumps(
        payload,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ).encode("utf-8")
    try:
        with temporary.open("xb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except Exception:
        if temporary.exists():
            temporary.unlink()
        raise


def write_text_create(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(value)
        handle.flush()
        os.fsync(handle.fileno())


def write_bytes_create(path: Path, value: bytes, max_bytes: int) -> tuple[str, int]:
    if not value or len(value) > max_bytes:
        raise KaraokeStorageError("File is empty or exceeds the size limit")
    if path.exists():
        raise KaraokeStorageError(f"Refusing to replace existing file: {path}")
    digest = hashlib.sha256(value).hexdigest()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        reader = io.BytesIO(value)
        for chunk in iter(lambda: reader.read(64 * 1024), b""):
            handle.write(chunk)
        handle.flush()
        os.fsync(handle.fileno())
    return digest, len(value)


def publish_staged_directory(stage: Path, destination: Path) -> None:
    if destination.exists():
        raise KaraokeStorageError(
            f"Karaoke library item already exists: {destination.name}"
        )
    destination.parent.mkdir(parents=True, exist_ok=True)
    os.replace(stage, destination)


def copy_create(source: Path, destination: Path, max_bytes: int) -> tuple[str, int]:
    if destination.exists():
        raise KaraokeStorageError(f"Refusing to replace existing file: {destination}")
    size = source.stat().st_size
    if size <= 0 or size > max_bytes:
        raise KaraokeStorageError("Subtitle file is empty or exceeds the size limit")
    digest = hashlib.sha256()
    destination.parent.mkdir(parents=True, exist_ok=True)
    with source.open("rb") as reader, destination.open("xb") as writer:
        for chunk in iter(lambda: reader.read(64 * 1024), b""):
            digest.update(chunk)
            writer.write(chunk)
        writer.flush()
        os.fsync(writer.fileno())
    return digest.hexdigest(), size


def mp4_integrity(path: Path) -> dict[str, int | bool | str | None]:
    """Validate top-level ISO BMFF boxes without decoding or rewriting media."""
    file_size = path.stat().st_size
    position = 0
    box_types: set[bytes] = set()
    expected_bytes: int | None = None
    reason = ""
    with path.open("rb") as handle:
        while position < file_size:
            if file_size - position < 8:
                reason = "trailing partial MP4 box header"
                break
            handle.seek(position)
            header = handle.read(8)
            size, box_type = struct.unpack(">I4s", header)
            header_size = 8
            if size == 1:
                extended = handle.read(8)
                if len(extended) != 8:
                    reason = "truncated extended MP4 box header"
                    break
                size = struct.unpack(">Q", extended)[0]
                header_size = 16
            elif size == 0:
                size = file_size - position
            if size < header_size:
                reason = "invalid MP4 box size"
                break
            box_end = position + size
            if box_end > file_size:
                expected_bytes = box_end
                reason = f"truncated {box_type.decode('latin1')} box"
                break
            box_types.add(box_type)
            position = box_end
    complete = (
        not reason
        and position == file_size
        and {b"ftyp", b"moov", b"mdat"}.issubset(box_types)
    )
    if not complete and not reason:
        reason = "required MP4 boxes are missing"
    return {
        "complete": complete,
        "actual_bytes": file_size,
        "expected_bytes": expected_bytes,
        "reason": reason or None,
    }


def create_video_thumbnail(video: Path, destination: Path) -> bool:
    """Create one local cover frame; failure leaves the item playable."""
    if destination.exists():
        return True
    command = [
        resolve_ffmpeg_executable(),
        "-hide_banner",
        "-loglevel",
        "error",
        "-ss",
        "00:00:05",
        "-i",
        str(video),
        "-frames:v",
        "1",
        "-vf",
        "scale='min(960,iw)':-2",
        "-y",
        str(destination),
    ]
    try:
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=60,
            check=False,
            creationflags=(
                getattr(subprocess, "CREATE_NO_WINDOW", 0)
                if os.name == "nt"
                else 0
            ),
            shell=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0 and destination.is_file()
