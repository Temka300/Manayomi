"""WebP cover thumbnails for the manga library (Pillow port of covers.ts)."""
from __future__ import annotations

import io
import logging
from pathlib import Path

from PIL import Image

from manga.cbz import first_image
from manga.paths import MANGA_COVERS_DIR, ensure_module_dirs

logger = logging.getLogger("keivotos")

COVER_WIDTH = 480
COVER_QUALITY = 82


def cover_file_name(gallery_id: int) -> str:
    return f"{int(gallery_id)}.webp"


def cover_path(gallery_id: int) -> Path:
    return MANGA_COVERS_DIR / cover_file_name(gallery_id)


def generate_cover(gallery_id: int, image_data: bytes) -> str | None:
    """Write a resized WebP cover into the covers cache; returns its file name."""
    ensure_module_dirs()
    try:
        with Image.open(io.BytesIO(image_data)) as image:
            image = image.convert("RGB")
            if image.width > COVER_WIDTH:
                height = max(1, round(image.height * COVER_WIDTH / image.width))
                image = image.resize((COVER_WIDTH, height), Image.LANCZOS)
            target = cover_path(gallery_id)
            temporary = target.with_suffix(".webp.tmp")
            image.save(temporary, "WEBP", quality=COVER_QUALITY)
        temporary.replace(target)
        return cover_file_name(gallery_id)
    except Exception as exc:  # noqa: BLE001 - a bad image must not sink a scan
        logger.warning("manga cover generation failed for %s: %s", gallery_id, exc)
        return None


def generate_cover_from_cbz(gallery_id: int, cbz_path: str | Path) -> str | None:
    """Cover from the first page of a CBZ; reuses an existing cached cover."""
    existing = cover_path(gallery_id)
    if existing.is_file():
        return cover_file_name(gallery_id)
    try:
        first = first_image(cbz_path)
    except Exception as exc:  # noqa: BLE001 - unreadable archive
        logger.warning("manga cover: unreadable CBZ %s: %s", cbz_path, exc)
        return None
    if first is None:
        return None
    return generate_cover(gallery_id, first[1])
