"""Manayomi remote Browse logical-page regression coverage."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from manga.browse_paging import (  # noqa: E402
    browse_window,
    exact_total,
    logical_page_count,
    normalize_page_size,
)
from routers import manga as manga_router  # noqa: E402


class BrowsePagingMathTests(unittest.TestCase):
    def test_logical_pages_span_fixed_upstream_pages(self) -> None:
        first = browse_window(1, 10)
        self.assertEqual((first.start, first.first_upstream_page, first.last_upstream_page, first.offset), (0, 1, 1, 0))

        crossing = browse_window(3, 10)
        self.assertEqual(
            (crossing.start, crossing.first_upstream_page, crossing.last_upstream_page, crossing.offset),
            (20, 1, 2, 20),
        )

        fifty = browse_window(2, 50)
        self.assertEqual(
            (fifty.start, fifty.first_upstream_page, fifty.last_upstream_page, fifty.offset),
            (50, 3, 4, 0),
        )

    def test_last_upstream_page_produces_exact_logical_counts(self) -> None:
        total = exact_total(3, 7)
        self.assertEqual(total, 57)
        self.assertEqual(logical_page_count(total, 10), 6)
        self.assertEqual(logical_page_count(total, 20), 3)
        self.assertEqual(logical_page_count(total, 30), 2)
        self.assertEqual(logical_page_count(total, 50), 2)
        self.assertEqual(normalize_page_size(999), 25)


class BrowsePagingApiTests(unittest.TestCase):
    def setUp(self) -> None:
        manga_router._browse_cache.clear()

    def tearDown(self) -> None:
        manga_router._browse_cache.clear()

    def test_api_aggregates_thirty_items_and_reports_exact_total(self) -> None:
        upstream = {
            1: [{"id": number, "tag_ids": []} for number in range(1, 26)],
            2: [{"id": number, "tag_ids": []} for number in range(26, 51)],
            3: [{"id": number, "tag_ids": []} for number in range(51, 58)],
        }

        def browse(_query: str, page: int, _sort: str, _language: str):
            return {"items": upstream[page], "num_pages": 3}

        with (
            patch.object(manga_router, "_nh_guard"),
            patch.object(
                manga_router,
                "get_manga_settings",
                return_value={"ignored_tags": [], "show_ignored": True},
            ),
            patch.object(manga_router.nhentai, "browse_galleries", side_effect=browse) as remote,
            patch.object(manga_router.queries, "downloaded_gallery_ids", return_value=set()),
            patch.object(manga_router.queries, "tag_info_by_nh_ids", return_value={}),
        ):
            first = manga_router.browse_nhentai(query="test", page=1, per_page=30)
            second = manga_router.browse_nhentai(query="test", page=2, per_page=30)

        self.assertEqual([item["id"] for item in first["items"]], list(range(1, 31)))
        self.assertEqual([item["id"] for item in second["items"]], list(range(31, 58)))
        self.assertEqual((first["total"], first["num_pages"], first["per_page"]), (57, 2, 30))
        self.assertTrue(first["has_more"])
        self.assertFalse(second["has_more"])
        self.assertEqual(remote.call_count, 3)

    def test_browse_marks_visible_blacklist_matches(self) -> None:
        items = [{"id": 10, "tag_ids": [7]}]
        with (
            patch.object(manga_router, "_nh_guard"),
            patch.object(
                manga_router,
                "get_manga_settings",
                return_value={"ignored_tags": ["Chinese"], "show_ignored": True},
            ),
            patch.object(
                manga_router.nhentai,
                "browse_galleries",
                return_value={"items": items, "num_pages": 1},
            ),
            patch.object(manga_router.queries, "downloaded_gallery_ids", return_value=set()),
            patch.object(
                manga_router.queries,
                "tag_info_by_nh_ids",
                return_value={7: {"name": "chinese", "category": "language"}},
            ),
        ):
            result = manga_router.browse_nhentai(page=1, per_page=20)

        self.assertEqual(result["items"][0]["ignored_matches"], ["chinese"])

    def test_hidden_blacklist_is_added_to_upstream_query(self) -> None:
        with (
            patch.object(manga_router, "_nh_guard"),
            patch.object(
                manga_router,
                "get_manga_settings",
                return_value={"ignored_tags": ["china", "rough translation"], "show_ignored": False},
            ),
            patch.object(
                manga_router.nhentai,
                "browse_galleries",
                return_value={"items": [], "num_pages": 1},
            ) as remote,
            patch.object(manga_router.queries, "downloaded_gallery_ids", return_value=set()),
            patch.object(manga_router.queries, "tag_info_by_nh_ids", return_value={}),
        ):
            manga_router.browse_nhentai(query="artist:test", page=1, per_page=20)

        self.assertEqual(remote.call_args.args[0], 'artist:test -china -"rough translation"')


if __name__ == "__main__":
    unittest.main()
