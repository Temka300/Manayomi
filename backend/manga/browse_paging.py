"""Logical Manayomi Browse pages over nHentai's fixed 25-item pages."""
from __future__ import annotations

from dataclasses import dataclass

UPSTREAM_PAGE_SIZE = 25
ALLOWED_PAGE_SIZES = {10, 20, 25, 30, 50}


@dataclass(frozen=True)
class BrowseWindow:
    page: int
    per_page: int
    start: int
    first_upstream_page: int
    last_upstream_page: int
    offset: int


def normalize_page_size(requested: int) -> int:
    return requested if requested in ALLOWED_PAGE_SIZES else UPSTREAM_PAGE_SIZE


def browse_window(page: int, per_page: int) -> BrowseWindow:
    page = max(1, page)
    per_page = normalize_page_size(per_page)
    start = (page - 1) * per_page
    first = start // UPSTREAM_PAGE_SIZE + 1
    offset = start % UPSTREAM_PAGE_SIZE
    last = (start + per_page - 1) // UPSTREAM_PAGE_SIZE + 1
    return BrowseWindow(page, per_page, start, first, last, offset)


def exact_total(upstream_pages: int, last_page_items: int) -> int:
    upstream_pages = max(1, upstream_pages)
    last_page_items = max(0, min(UPSTREAM_PAGE_SIZE, last_page_items))
    return (upstream_pages - 1) * UPSTREAM_PAGE_SIZE + last_page_items


def logical_page_count(total: int, per_page: int) -> int:
    size = normalize_page_size(per_page)
    return max(1, (max(0, total) + size - 1) // size)
