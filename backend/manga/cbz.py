"""CBZ archive helpers built on the standard-library zipfile module."""
from __future__ import annotations

import re
import zipfile
from pathlib import Path
from typing import Iterable

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif"}


def _natural_key(name: str) -> list[object]:
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", name)]


def build_cbz(cbz_path: str | Path, entries: list[tuple[str, bytes]]) -> None:
    """Write a CBZ from (name, data) pairs. Images are stored uncompressed —
    they are already compressed formats, and STORED keeps reads fast."""
    path = Path(cbz_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".cbz.tmp")
    with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_STORED) as archive:
        for name, data in entries:
            archive.writestr(name, data)
    temporary.replace(path)


def build_cbz_stream(cbz_path: str | Path, entries: Iterable[tuple[str, bytes]]) -> None:
    """Atomically build a CBZ while consuming one page at a time.

    Long MangaDex chapters therefore do not keep every compressed page in RAM.
    The final archive is replaced only after the iterator completes cleanly.
    """
    path = Path(cbz_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".cbz.tmp")
    with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_STORED) as archive:
        for name, data in entries:
            archive.writestr(name, data)
    temporary.replace(path)


def list_images(cbz_path: str | Path) -> list[str]:
    """Image entry names inside a CBZ, naturally sorted."""
    with zipfile.ZipFile(cbz_path) as archive:
        names = [
            info.filename
            for info in archive.infolist()
            if not info.is_dir() and Path(info.filename).suffix.lower() in IMAGE_EXTENSIONS
        ]
    return sorted(names, key=_natural_key)


def read_entry(cbz_path: str | Path, name: str) -> bytes:
    with zipfile.ZipFile(cbz_path) as archive:
        return archive.read(name)


def first_image(cbz_path: str | Path) -> tuple[str, bytes] | None:
    names = list_images(cbz_path)
    if not names:
        return None
    return names[0], read_entry(cbz_path, names[0])


CONTENT_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".avif": "image/avif",
}


def content_type_for(name: str) -> str:
    return CONTENT_TYPES.get(Path(name).suffix.lower(), "application/octet-stream")
