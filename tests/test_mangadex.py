"""MangaDex provider, identity, and local scan characterization."""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from manga import mangadex  # noqa: E402
from manga.manatan import mangadex_chapter_paths_for  # noqa: E402

TITLE_ID = "f9c33607-9180-4ba6-b85c-e4b5faee7192"
CHAPTER_ID = "e5d7e2c4-ae9c-4f45-b173-8289f66ec4db"
SECOND_CHAPTER_ID = "08aa4f99-60b0-4c98-9c0f-2d73e30be0f0"


class MangaDexProviderTests(unittest.TestCase):
    def test_title_and_chapter_normalization_preserve_hierarchy_and_groups(self) -> None:
        title = mangadex.normalize_title(
            {
                "id": TITLE_ID,
                "attributes": {
                    "title": {"ja": "日本語", "en": "Test Manga"},
                    "description": {"en": "Description"},
                    "status": "ongoing",
                    "year": 2024,
                    "originalLanguage": "ja",
                    "availableTranslatedLanguages": ["en", "ja"],
                    "contentRating": "safe",
                    "tags": [
                        {
                            "id": CHAPTER_ID,
                            "attributes": {"name": {"en": "Adventure"}, "group": "genre"},
                        }
                    ],
                },
                "relationships": [
                    {"type": "author", "attributes": {"name": "Writer"}},
                    {"type": "artist", "attributes": {"name": "Artist"}},
                    {"type": "cover_art", "attributes": {"fileName": "cover.jpg"}},
                ],
            }
        )
        chapter = mangadex.normalize_chapter(
            {
                "id": CHAPTER_ID,
                "attributes": {
                    "title": "Arrival",
                    "volume": "1",
                    "chapter": "2",
                    "pages": 22,
                    "translatedLanguage": "en",
                    "publishAt": "2026-01-01T00:00:00+00:00",
                },
                "relationships": [
                    {"type": "manga", "id": TITLE_ID},
                    {"type": "scanlation_group", "attributes": {"name": "Group A"}},
                ],
            }
        )
        self.assertEqual(title["title"], "Test Manga")
        self.assertEqual(title["cover_filename"], "cover.jpg")
        self.assertEqual(chapter["manga_id"], TITLE_ID)
        self.assertEqual(chapter["scanlation_groups"], ["Group A"])
        library = mangadex.library_gallery(title, chapter, -1)
        self.assertEqual(library["external_id"], CHAPTER_ID)
        self.assertEqual(library["parent_external_id"], TITLE_ID)
        self.assertIn("Ch. 2", library["title"]["pretty"])

    def test_search_uses_offset_expansions_language_and_official_excluded_tags(self) -> None:
        captured: list[tuple[str, str]] = []

        def api(_path: str, *, params=None, timeout=30.0):
            del timeout
            captured.extend(params or [])
            return {"data": [], "total": 41}

        with (
            patch.object(mangadex, "_api_json", side_effect=api),
            patch.object(mangadex, "tag_ids_for_names", return_value=[CHAPTER_ID]),
        ):
            result = mangadex.search_titles(
                "test", page=3, per_page=20, sort="rating", language="en", excluded_tag_names=["gore"]
            )

        self.assertEqual(result["num_pages"], 3)
        self.assertIn(("offset", "40"), captured)
        self.assertIn(("includes[]", "cover_art"), captured)
        self.assertIn(("availableTranslatedLanguage[]", "en"), captured)
        self.assertIn(("excludedTags[]", CHAPTER_ID), captured)
        self.assertIn(("excludedTagsMode", "OR"), captured)
        self.assertIn(("order[rating]", "desc"), captured)

    def test_search_maps_every_structured_filter_to_the_mangadex_contract(self) -> None:
        captured: list[tuple[str, str]] = []

        def api(_path: str, *, params=None, timeout=30.0):
            del timeout
            captured.extend(params or [])
            return {"data": [], "total": 0}

        with (
            patch.object(mangadex, "_api_json", side_effect=api),
            patch.object(mangadex, "tag_ids_for_names", return_value=[]),
        ):
            mangadex.search_titles(
                "hero",
                sort="title-desc",
                language="en",
                original_languages=["ja", "ko"],
                content_ratings=["safe", "suggestive"],
                publication_demographics=["shounen"],
                statuses=["ongoing", "hiatus"],
                included_tag_ids=[CHAPTER_ID],
                tags_mode="OR",
            )

        for expected in (
            ("originalLanguage[]", "ja"),
            ("originalLanguage[]", "ko"),
            ("contentRating[]", "safe"),
            ("contentRating[]", "suggestive"),
            ("publicationDemographic[]", "shounen"),
            ("status[]", "ongoing"),
            ("status[]", "hiatus"),
            ("includedTags[]", CHAPTER_ID),
            ("includedTagsMode", "OR"),
            ("order[title]", "desc"),
        ):
            self.assertIn(expected, captured)
        self.assertNotIn(("contentRating[]", "pornographic"), captured)

    def test_filter_catalog_uses_live_mangadex_tag_names_and_groups(self) -> None:
        body = {
            "data": [
                {
                    "id": TITLE_ID,
                    "attributes": {"name": {"en": "Gore"}, "group": "content"},
                },
                {
                    "id": CHAPTER_ID,
                    "attributes": {"name": {"en": "Adventure"}, "group": "genre"},
                },
            ]
        }
        with (
            patch.object(mangadex, "_tag_cache", None),
            patch.object(mangadex, "_api_json", return_value=body),
        ):
            catalog = mangadex.filter_catalog()

        self.assertEqual(catalog["tag_groups"]["content"][0]["name"], "Gore")
        self.assertEqual(catalog["tag_groups"]["genre"][0]["name"], "Adventure")
        self.assertTrue(catalog["tag_groups"]["format"] == [])
        self.assertIn({"value": "shounen", "label": "Shounen"}, catalog["publication_demographics"])
        self.assertIn({"value": "AND", "label": "Match all"}, catalog["tag_modes"])

    def test_invalid_filter_values_are_rejected_before_the_network(self) -> None:
        with patch.object(mangadex, "_api_json") as api:
            with self.assertRaises(mangadex.MangaDexError) as raised:
                mangadex.search_titles(statuses=["finished"])
        self.assertEqual(raised.exception.status, 400)
        api.assert_not_called()

    def test_at_home_page_fetch_uses_requested_quality_and_reports_transfer(self) -> None:
        response = Mock()
        response.ok = True
        response.content = b"image"
        response.headers = {"content-type": "image/jpeg", "X-Cache": "HIT"}
        home = {
            "base_url": "https://node.example",
            "hash": "digest",
            "data": ["001.jpg"],
            "data_saver": ["001-s.jpg"],
        }
        with (
            patch.object(mangadex, "_at_home", return_value=home),
            patch.object(mangadex._session, "get", return_value=response) as get,
            patch.object(mangadex, "_report_image") as report,
        ):
            data, content_type, name = mangadex.fetch_chapter_page(CHAPTER_ID, 0, "data-saver")

        self.assertEqual((data, content_type, name), (b"image", "image/jpeg", "001-s.jpg"))
        self.assertEqual(
            get.call_args.args[0],
            "https://node.example/data-saver/digest/001-s.jpg",
        )
        self.assertTrue(report.call_args.args[2])

    def test_chapter_feed_uses_numeric_boolean_flags_required_by_api(self) -> None:
        captured: list[tuple[str, str]] = []

        def api(_path: str, *, params=None, timeout=30.0):
            del timeout
            captured.extend(params or [])
            return {"data": [], "total": 0}

        with patch.object(mangadex, "_api_json", side_effect=api):
            mangadex.list_chapters(TITLE_ID)

        self.assertIn(("includeEmptyPages", "0"), captured)
        self.assertIn(("includeFuturePublishAt", "0"), captured)
        self.assertIn(("includeUnavailable", "0"), captured)

    def test_mangadex_path_keeps_both_uuids(self) -> None:
        paths = mangadex_chapter_paths_for(
            "C:/library",
            {"id": TITLE_ID, "title": "A: Title"},
            {"id": CHAPTER_ID, "translated_language": "en", "volume": "1", "chapter": "2"},
        )
        self.assertIn(f"--m{TITLE_ID}", str(paths["manga_dir"]))
        self.assertIn(f"--c{CHAPTER_ID}", str(paths["chapter_dir"]))
        self.assertEqual(paths["cbz_path"].name, "chapter.cbz")


class MangaDexSurfaceContractTests(unittest.TestCase):
    def test_provider_selector_title_chapters_reader_and_download_contract(self) -> None:
        manga = ROOT / "frontend" / "src" / "components" / "manga"
        wrapper = (manga / "MangaBrowseProviders.svelte").read_text(encoding="utf-8")
        browse = (manga / "MangaDexBrowse.svelte").read_text(encoding="utf-8")
        filters = (manga / "MangaDexFilterSheet.svelte").read_text(encoding="utf-8")
        detail = (manga / "MangaDexDetailOverlay.svelte").read_text(encoding="utf-8")
        view = (manga / "MangaView.svelte").read_text(encoding="utf-8")
        router = (ROOT / "backend" / "routers" / "manga.py").read_text(encoding="utf-8")

        self.assertIn('aria-label="Browse source"', wrapper)
        self.assertIn(">nHentai</button>", wrapper)
        self.assertIn(">MangaDex</button>", wrapper)
        self.assertIn("mangaDexBrowse", browse)
        self.assertIn("Search MangaDex titles", browse)
        self.assertIn("downloaded_chapters", browse)
        for label in (
            "Original language", "Content rating", "Publication demographic",
            "Status", "Sort", "Tags mode", "Content", "Format", "Genre", "Theme",
        ):
            self.assertIn(label, filters)
        self.assertIn("mangaDexFilters", browse)
        self.assertIn("mobile-detail-tabs", detail)
        self.assertIn("No public chapters found.", detail)
        self.assertIn("chapterError", detail)
        self.assertIn("translations and groups stay separate", detail)
        self.assertIn("scanlation_groups", detail)
        self.assertIn("downloadSelected", detail)
        self.assertIn("mangaDexPageUrl", detail)
        self.assertIn("readerMode === 'paged'", detail)
        self.assertIn("readerMode === 'scroll'", detail)
        self.assertIn("openMangaDexChapter", view)
        for route in (
            '/api/manga/remote/mangadex/browse',
            '/api/manga/remote/mangadex/filters',
            '/api/manga/remote/mangadex/title/{title_id}',
            '/api/manga/remote/mangadex/title/{title_id}/chapters',
            '/api/manga/remote/mangadex/chapter/{chapter_id}/pages',
            '/api/manga/remote/mangadex/download/{chapter_id}',
        ):
            self.assertIn(route, router)


MANGADEX_SCAN_SCRIPT = r"""
import io, sys, time, zipfile
from pathlib import Path
from PIL import Image

sys.path.insert(0, sys.argv[1])
root = Path(sys.argv[2])
title_id, chapter_id, second_id = sys.argv[3:6]

from manga.database import remote_external_id, remote_gallery_id
from manga.mangadex import write_download_sidecar
from manga.manatan import mangadex_chapter_paths_for
from manga.queries import get_manga_by_external_id, reading_history, save_reading_progress, search_library
from manga.roots import add_root
from manga.scanner import scan_progress, start_scan
from manga.search import parse_library_query

title = {
    "id": title_id, "title": "MangaDex Test", "titles": {"en": "MangaDex Test"},
    "alternate_titles": [], "description": "", "authors": ["Writer"], "artists": ["Artist"],
    "cover_filename": "cover.jpg", "tags": [{"id": chapter_id, "name": "Adventure", "group": "genre"}],
    "status": "ongoing", "year": 2026, "original_language": "ja", "available_languages": ["en"],
    "content_rating": "safe", "publication_demographic": "shounen", "last_volume": None,
    "last_chapter": None, "links": {}, "official_links": [], "created_at": None, "updated_at": None,
}
chapter = {
    "id": chapter_id, "manga_id": title_id, "title": "Arrival", "volume": "1", "chapter": "2",
    "pages": 1, "translated_language": "en", "external_url": "", "publish_at": "2026-01-01T00:00:00+00:00",
    "readable_at": None, "created_at": None, "updated_at": None, "unavailable": False,
    "scanlation_groups": ["Group A"],
}
paths = mangadex_chapter_paths_for(root, title, chapter)
paths["chapter_dir"].mkdir(parents=True)
buffer = io.BytesIO()
Image.new("RGB", (24, 36), (80, 100, 200)).save(buffer, "PNG")
with zipfile.ZipFile(paths["cbz_path"], "w") as archive:
    archive.writestr("page_0.png", buffer.getvalue())
write_download_sidecar(paths["cbz_path"], title, chapter)

first = remote_gallery_id("mangadex", chapter_id, create=True)
assert first == -1 and remote_gallery_id("mangadex", chapter_id, create=True) == first
second = remote_gallery_id("mangadex", second_id, create=True)
assert second == -2 and remote_external_id("mangadex", second) == second_id

added = add_root(str(root))
assert added["ok"], added
assert start_scan(added["root"]["id"], enrich=False)
for _ in range(100):
    if not scan_progress()["running"]:
        break
    time.sleep(.05)
progress = scan_progress()
assert progress["added"] == 1 and progress["matched"] == 1, progress
card = get_manga_by_external_id(chapter_id, "mangadex")
assert card and card["gallery_id"] == first and card["parent_external_id"] == title_id, card
found = search_library(parse_library_query("Adventure"))
assert found["total"] == 1 and found["manga"][0]["source"] == "mangadex", found
save_reading_progress(first, title="MangaDex Test — Ch. 2", cover_path="/cover", last_page=0, page_count=1, source="mangadex")
history = reading_history(limit=5)
assert history["items"][0]["external_id"] == chapter_id, history
print("MANGADEX_SCAN_OK")
"""


class MangaDexIdentityIntegrationTests(unittest.TestCase):
    def test_uuid_identity_survives_scan_and_joins_library_history(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary) / "home"
            library = Path(temporary) / "library"
            library.mkdir()
            completed = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    MANGADEX_SCAN_SCRIPT,
                    str(BACKEND),
                    str(library),
                    TITLE_ID,
                    CHAPTER_ID,
                    SECOND_CHAPTER_ID,
                ],
                capture_output=True,
                text=True,
                timeout=120,
                env={**os.environ, "KEIVOTOS_HOME": str(home)},
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertIn("MANGADEX_SCAN_OK", completed.stdout)


if __name__ == "__main__":
    unittest.main()
