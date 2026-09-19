"""Fast, read-only CBZ page delivery for the Manayomi reader."""
from __future__ import annotations

from collections import OrderedDict
from io import BytesIO
from pathlib import Path
from threading import RLock

from PIL import Image, ImageOps

from manga.cbz import content_type_for, list_images, read_entry

_PAGE_LIST_LIMIT = 32
_FAST_ENTRY_LIMIT = 80
_FAST_BYTE_LIMIT = 128 * 1024 * 1024

_cache_lock = RLock()
_page_lists: OrderedDict[tuple[str, int, int], tuple[str, tuple[str, ...]]] = OrderedDict()
_fast_pages: OrderedDict[tuple[str, int, int, str, int], bytes] = OrderedDict()
_fast_page_bytes = 0


def _identity(cbz_path: str | Path) -> tuple[Path, tuple[str, int, int], str]:
    path = Path(cbz_path).resolve()
    stat = path.stat()
    key = (str(path), stat.st_mtime_ns, stat.st_size)
    version = f"{stat.st_mtime_ns:x}-{stat.st_size:x}"
    return path, key, version


def archive_pages(cbz_path: str | Path) -> tuple[str, tuple[str, ...]]:
    """Return a version token and naturally sorted page names from a bounded cache."""
    path, key, version = _identity(cbz_path)
    with _cache_lock:
        cached = _page_lists.get(key)
        if cached is not None:
            _page_lists.move_to_end(key)
            return cached

    result = (version, tuple(list_images(path)))
    with _cache_lock:
        for stale_key in [item for item in _page_lists if item[0] == key[0] and item != key]:
            _page_lists.pop(stale_key, None)
        _page_lists[key] = result
        _page_lists.move_to_end(key)
        while len(_page_lists) > _PAGE_LIST_LIMIT:
            _page_lists.popitem(last=False)
    return result


def _fast_webp(source: bytes, max_width: int) -> bytes:
    with Image.open(BytesIO(source)) as opened:
        image = ImageOps.exif_transpose(opened)
        image.load()
        if image.width > max_width:
            height = max(1, round(image.height * max_width / image.width))
            image = image.resize((max_width, height), Image.Resampling.LANCZOS)
        if image.mode not in {"RGB", "RGBA"}:
            image = image.convert("RGBA" if "transparency" in image.info else "RGB")
        output = BytesIO()
        image.save(output, format="WEBP", quality=82, method=1)
        return output.getvalue()


def _remember_fast(key: tuple[str, int, int, str, int], data: bytes) -> None:
    global _fast_page_bytes
    if len(data) > _FAST_BYTE_LIMIT:
        return
    with _cache_lock:
        previous = _fast_pages.pop(key, None)
        if previous is not None:
            _fast_page_bytes -= len(previous)
        _fast_pages[key] = data
        _fast_page_bytes += len(data)
        while _fast_pages and (
            len(_fast_pages) > _FAST_ENTRY_LIMIT or _fast_page_bytes > _FAST_BYTE_LIMIT
        ):
            _, evicted = _fast_pages.popitem(last=False)
            _fast_page_bytes -= len(evicted)


def read_page(
    cbz_path: str | Path,
    number: int,
    *,
    max_width: int = 0,
) -> tuple[bytes, str, str, str]:
    """Read one zero-based page as original bytes or a phone-sized WebP."""
    path, identity, version = _identity(cbz_path)
    cached_version, names = archive_pages(path)
    if number < 0 or number >= len(names):
        raise IndexError(number)
    name = names[number]
    if max_width <= 0:
        return read_entry(path, name), content_type_for(name), cached_version, name

    width = max(320, min(2400, max_width))
    cache_key = (*identity, name, width)
    with _cache_lock:
        cached = _fast_pages.get(cache_key)
        if cached is not None:
            _fast_pages.move_to_end(cache_key)
            return cached, "image/webp", version, name

    source = read_entry(path, name)
    with Image.open(BytesIO(source)) as image:
        if image.width <= width:
            return source, content_type_for(name), version, name

    data = _fast_webp(source, width)
    _remember_fast(cache_key, data)
    return data, "image/webp", version, name


def clear_reader_caches() -> None:
    """Clear process-memory caches (used by isolated regression tests)."""
    global _fast_page_bytes
    with _cache_lock:
        _page_lists.clear()
        _fast_pages.clear()
        _fast_page_bytes = 0
