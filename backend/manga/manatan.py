"""Manatan-style on-disk layout helpers.

The user's existing hoard (``D:\\Kivotos\\Japan\\manga_heh``) nests manga
directly under the library root — no per-source wrapper folder:

    <root>/<title>--m<mangaId>/<category> - Chapter--c<chapterId>/
        chapter.cbz          (the pages)
        manifest.json        {"pages":[...],"archive_file":"chapter.cbz"}
        nhentai.json         full nHentai metadata (portability + rescans)

nHentai doujinshi are a single chapter, so manga id == chapter id ==
gallery id, and the id is recoverable from the folder name alone.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from manga.nhentai import best_title, category_of

ARCHIVE_FILE = "chapter.cbz"
MANIFEST_FILE = "manifest.json"
NHENTAI_META_FILE = "nhentai.json"
MANGADEX_META_FILE = "mangadex.json"

MAX_SEGMENT = 180  # keep folder names inside Windows path limits


def sanitize_segment(name: str) -> str:
    """Make a string safe as a single Windows/POSIX path segment."""
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name or "")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    cleaned = re.sub(r"[. ]+$", "", cleaned)
    if len(cleaned) > MAX_SEGMENT:
        cleaned = cleaned[:MAX_SEGMENT].strip()
    return cleaned or "Untitled"


def chapter_paths_for(root: str | Path, gallery: dict[str, Any]) -> dict[str, Path]:
    """Resolve the folder tree for a gallery under ``root``."""
    title = sanitize_segment(best_title(gallery))
    category = sanitize_segment(category_of(gallery))
    gallery_id = int(gallery["id"])
    manga_dir = Path(root) / f"{title}--m{gallery_id}"
    chapter_dir = manga_dir / f"{category} - Chapter--c{gallery_id}"
    return {
        "manga_dir": manga_dir,
        "chapter_dir": chapter_dir,
        "cbz_path": chapter_dir / ARCHIVE_FILE,
    }


def mangadex_chapter_paths_for(
    root: str | Path,
    title: dict[str, Any],
    chapter: dict[str, Any],
) -> dict[str, Path]:
    """Resolve a MangaDex title/chapter tree without shortening either UUID."""
    title_id = str(title["id"]).lower()
    chapter_id = str(chapter["id"]).lower()
    title_segment = sanitize_segment(str(title.get("title") or "Untitled"))
    language = sanitize_segment(str(chapter.get("translated_language") or "und").upper())
    number = chapter.get("chapter")
    volume = chapter.get("volume")
    label_parts = [language]
    if volume not in (None, ""):
        label_parts.append(f"Vol. {volume}")
    label_parts.append(f"Chapter {number}" if number not in (None, "") else "Unnumbered chapter")
    chapter_segment = sanitize_segment(" - ".join(label_parts))
    manga_dir = Path(root) / f"{title_segment}--m{title_id}"
    chapter_dir = manga_dir / f"{chapter_segment}--c{chapter_id}"
    return {
        "manga_dir": manga_dir,
        "chapter_dir": chapter_dir,
        "cbz_path": chapter_dir / ARCHIVE_FILE,
    }


def page_name(index: int, ext: str) -> str:
    """Manatan page name for a 0-based index, e.g. (0, "webp") -> "page_0.webp"."""
    return f"page_{index}.{ext}"


def write_manifest(chapter_dir: str | Path, pages: list[str]) -> None:
    body = json.dumps({"pages": pages, "archive_file": ARCHIVE_FILE})
    (Path(chapter_dir) / MANIFEST_FILE).write_text(body, encoding="utf-8")


def id_from_segment(segment: str) -> int | None:
    """Gallery id encoded in a ``--m<id>`` or ``--c<id>`` folder suffix."""
    match = re.search(r"--[mc](\d+)$", segment)
    return int(match.group(1)) if match else None
