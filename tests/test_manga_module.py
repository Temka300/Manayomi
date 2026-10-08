"""Manayomi manga-module tests: search parser, Manatan layout, and an
isolated end-to-end scan (temp KEIVOTOS_HOME + temp library root)."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from manga.manatan import id_from_segment, page_name, sanitize_segment  # noqa: E402
from manga.nhentai import SORT_TO_V2, parse_tag_directory  # noqa: E402
from manga.search import parse_library_query  # noqa: E402


class MangaSearchParserTests(unittest.TestCase):
    def test_bare_words_are_any_category_tags(self) -> None:
        query = parse_library_query("big breasts glasses")
        self.assertEqual(query.include, ["big", "breasts", "glasses"])
        self.assertEqual(query.exclude, [])

    def test_quoted_tags_stay_together_and_negate(self) -> None:
        query = parse_library_query('"big breasts" -"story arc"')
        self.assertEqual(query.include, ["big breasts"])
        self.assertEqual(query.exclude, ["story arc"])

    def test_scoped_numeric_date_and_title_filters(self) -> None:
        query = parse_library_query(
            'artist:foo -character:"bar baz" pages:>20 favorites:>=100 uploaded:<2w title:"hello there" jtitle:"日本"'
        )
        self.assertEqual(
            [(s.category, s.name, s.negate) for s in query.scoped],
            [("artist", "foo", False), ("character", "bar baz", True)],
        )
        assert query.pages and query.favorites and query.uploaded
        self.assertEqual((query.pages.op, query.pages.value), (">", 20))
        self.assertEqual((query.favorites.op, query.favorites.value), (">=", 100))
        self.assertEqual((query.uploaded.op, query.uploaded.days), ("<", 14))
        self.assertEqual(query.title, "hello there")
        self.assertEqual(query.jtitle, "日本")

    def test_tag_prefix_matches_any_category(self) -> None:
        query = parse_library_query("tag:yuri -tags:netorare")
        self.assertEqual(query.include, ["yuri"])
        self.assertEqual(query.exclude, ["netorare"])


class ManatanLayoutTests(unittest.TestCase):
    def test_sanitize_segment_strips_illegal_windows_characters(self) -> None:
        self.assertEqual(sanitize_segment('a<b>:c"/d\\e|f?g*h'), "a_b__c__d_e_f_g_h")
        self.assertEqual(sanitize_segment("  trailing dots.. "), "trailing dots")
        self.assertEqual(sanitize_segment(""), "Untitled")
        self.assertLessEqual(len(sanitize_segment("x" * 500)), 180)

    def test_id_from_segment(self) -> None:
        self.assertEqual(id_from_segment("Some Title--m571323"), 571323)
        self.assertEqual(id_from_segment("doujinshi - Chapter--c380609"), 380609)
        self.assertIsNone(id_from_segment("no id here"))

    def test_page_name(self) -> None:
        self.assertEqual(page_name(0, "webp"), "page_0.webp")


class MangaBrowseContractTests(unittest.TestCase):
    def test_month_popularity_uses_the_upstream_v2_sort(self) -> None:
        self.assertEqual(SORT_TO_V2["popular-month"], "popular-month")

    def test_heh_tag_directory_parses_provider_names_and_global_counts(self) -> None:
        document = """
        <a class="tag" href="/tag/sole-female/">
          <span class="name">Sole Female</span><span class="count">198.9K</span>
        </a>
        <a class="tag" href="https://nhentai.net/tag/story-arc/">
          <span class="name">Story Arc</span><span class="count">24,300</span>
        </a>
        """
        self.assertEqual(
            parse_tag_directory(document),
            [
                {"name": "sole female", "slug": "sole-female", "count": 198_900},
                {"name": "story arc", "slug": "story-arc", "count": 24_300},
            ],
        )

    def test_browse_filter_and_gallery_code_contract(self) -> None:
        manga = ROOT / "frontend" / "src" / "components" / "manga"
        source = (manga / "MangaBrowse.svelte").read_text(
            encoding="utf-8"
        )
        sheet = (manga / "MangaFilterSheet.svelte").read_text(encoding="utf-8")
        for prefix in ("tag", "category", "group", "artist", "parody", "character"):
            self.assertIn(f"prefix: '{prefix}'", source)
        self.assertIn(".split(',')", source)
        self.assertIn("entry.includes(' ')", source)
        self.assertIn('if (/^\\d{1,6}$/.test(value))', source)
        self.assertIn("top-full", sheet)
        self.assertIn("h-7 w-full", sheet)
        self.assertIn("width: min(17rem, calc(100vw - 1rem))", sheet)
        self.assertIn("translate3d(-0.75rem, -0.2rem, 0)", sheet)
        self.assertIn("animation: filter-popover-in 180ms", sheet)

    def test_detail_tag_handoff_populates_the_originating_filter(self) -> None:
        manga = ROOT / "frontend" / "src" / "components" / "manga"
        library = (manga / "MangaLibrary.svelte").read_text(encoding="utf-8")
        browse = (manga / "MangaBrowse.svelte").read_text(encoding="utf-8")
        detail = (manga / "MangaDetailOverlay.svelte").read_text(encoding="utf-8")
        view = (manga / "MangaView.svelte").read_text(encoding="utf-8")

        self.assertIn("dispatch('searchTag', { category: tag.category, name: tag.name })", detail)
        for category, field in (
            ("tag", "tags"),
            ("category", "categories"),
            ("group", "groups"),
            ("artist", "artists"),
            ("parody", "parodies"),
            ("character", "characters"),
        ):
            self.assertIn(f"{category}: '{field}'", view)
        self.assertIn("initialFilter={pendingLibraryFilter}", view)
        self.assertIn("initialFilter={pendingBrowseFilter}", view)

        query_assignment = library.index("filters = { ...filters, [initialFilter.key]: initialFilter.value }")
        first_load = library.index("void load()", query_assignment)
        self.assertLess(query_assignment, library.index("await tick()", query_assignment, first_load))
        self.assertIn("filterOpen = true", library[query_assignment:first_load])
        browse_assignment = browse.index("filters = { ...filters, [initialFilter.key]: initialFilter.value }")
        self.assertIn("filterOpen = true", browse[browse_assignment:browse.index("void load()", browse_assignment)])

    def test_display_sizes_are_persisted_and_shared(self) -> None:
        view = (ROOT / "frontend" / "src" / "components" / "manga" / "MangaView.svelte").read_text(
            encoding="utf-8"
        )
        library = (ROOT / "frontend" / "src" / "components" / "manga" / "MangaLibrary.svelte").read_text(
            encoding="utf-8"
        )
        detail = (ROOT / "frontend" / "src" / "components" / "manga" / "MangaDetailOverlay.svelte").read_text(
            encoding="utf-8"
        )
        self.assertIn("manayomi:cover-size", view)
        self.assertIn("manayomi:info-size", view)
        self.assertIn("class:cover-small={coverSize === 'small'}", library)
        self.assertIn("class:info-large={infoSize === 'large'}", detail)

    def test_library_filters_pager_and_lan_reader_contract(self) -> None:
        manga = ROOT / "frontend" / "src" / "components" / "manga"
        library = (manga / "MangaLibrary.svelte").read_text(encoding="utf-8")
        browse = (manga / "MangaBrowse.svelte").read_text(encoding="utf-8")
        detail = (manga / "MangaDetailOverlay.svelte").read_text(encoding="utf-8")
        router = (ROOT / "backend" / "routers" / "manga.py").read_text(encoding="utf-8")

        for prefix in ("tag", "category", "group", "artist", "parody", "character"):
            self.assertIn(f"prefix: '{prefix}'", library)
        self.assertIn(".split(',')", library)
        self.assertIn("titleToken(q)", library)
        self.assertIn("Search titles or gallery number", library)
        self.assertIn("class=\"library-pager", library)
        for value in (10, 20, 30, 50):
            self.assertIn(f'<option value={{{value}}}>{value}</option>', library)
            self.assertIn(f'<option value={{{value}}}>{value}</option>', browse)
        self.assertIn('<option value="all">All</option>', library)
        self.assertIn('<option value="all">All</option>', browse)
        self.assertIn("perPage === 'all' ? 0 : perPage", library)
        self.assertIn("perPage === 'all' ? 25 : perPage", browse)
        self.assertIn("use:observeInfinite", browse)
        self.assertIn('class="browse-pager z-20', browse)
        self.assertIn('loading="lazy"', browse)

        self.assertIn("persist('reader-quality', readerQuality)", detail)
        self.assertIn("readerQuality === 'fast' ? 1600 : 0", detail)
        self.assertIn("pageUrls[pageIndex + 2]", detail)
        self.assertIn("Open on nHentai", detail)
        self.assertIn("Open in Files", detail)
        self.assertIn('aria-label="Read manga"', detail)
        self.assertGreaterEqual(detail.count('class="icon-action grid h-10 w-10'), 5)
        self.assertNotIn('class="ml-auto flex items-center gap-2"', detail)
        self.assertNotIn(">Read</button>", detail)
        self.assertIn(">Downloaded</dt>", detail)
        self.assertIn("downloadItem?.status === 'done'", detail)
        self.assertIn('aria-label={blur && !revealCover ? \'Reveal manga cover\' : \'Manga cover\'}', detail)
        self.assertNotIn("Blacklisted manga cover hidden", detail)
        local_lookup = router.index("local = queries.get_manga_by_gallery_id(gallery_id)")
        remote_guard = router.index("_nh_guard()", router.index("def remote_gallery"))
        self.assertLess(local_lookup, remote_guard)
        self.assertIn('max-age=31536000, immutable', router)

    def test_manayomi_phone_layout_and_touch_reader_contract(self) -> None:
        app = (ROOT / "frontend" / "src" / "App.svelte").read_text(encoding="utf-8")
        app_css = (ROOT / "frontend" / "src" / "app.css").read_text(encoding="utf-8")
        components = ROOT / "frontend" / "src" / "components"
        manga = components / "manga"
        view = (manga / "MangaView.svelte").read_text(encoding="utf-8")
        browse = (manga / "MangaBrowse.svelte").read_text(encoding="utf-8")
        library = (manga / "MangaLibrary.svelte").read_text(encoding="utf-8")
        downloads = (manga / "MangaDownloads.svelte").read_text(encoding="utf-8")
        settings = (manga / "MangaSettings.svelte").read_text(encoding="utf-8")
        detail = (manga / "MangaDetailOverlay.svelte").read_text(encoding="utf-8")
        danbooru_surface = (ROOT / "frontend" / "src" / "modules" / "danbooru" / "DanbooruSurface.svelte").read_text(
            encoding="utf-8"
        )
        manayomi_surface = (ROOT / "frontend" / "src" / "modules" / "manayomi" / "ManayomiSurface.svelte").read_text(
            encoding="utf-8"
        )

        self.assertIn('class="flex h-full min-h-0 flex-col', app)
        self.assertNotIn("h-screen", app)
        self.assertGreaterEqual(app_css.count("height: 100dvh"), 2)
        self.assertIn('"brand actions"', view)
        self.assertIn('aria-label="Open Keivotos menu"', view)
        self.assertIn("<AppDrawer", view)
        self.assertIn('"tabs tabs"', view)
        self.assertIn("scroll-snap-type: x proximity", view)
        self.assertIn("keepActiveTabVisible", view)
        self.assertIn("width: min(18rem, calc(100vw - 1rem))", view)
        self.assertNotIn("browse-control-strip", browse)
        self.assertIn("grid-template-columns: repeat(5, minmax(0, 1fr))", view)
        self.assertIn("position: fixed", view)
        self.assertIn("hide-downloaded", view)
        self.assertNotIn("touch-action: pan-x", browse)
        self.assertIn("on:keydown={onSearchKeydown}", browse)
        self.assertIn("repeat(3, minmax(0, 1fr))", browse)
        self.assertIn("repeat(1, minmax(0, 1fr))", browse)
        self.assertIn("window.matchMedia('(max-width: 1023px)').matches", library)
        self.assertIn("manga-library-sidebar", library)
        self.assertIn("grid-template-columns: 2rem 2rem minmax(0, 1fr)", library)
        self.assertIn("grid-template-columns: repeat(2, minmax(0, 1fr))", library)
        self.assertIn("on:keydown={onSearchKeydown}", library)
        self.assertIn("flex min-w-0 flex-wrap", downloads)
        self.assertGreaterEqual(settings.count("flex flex-col gap-2 sm:flex-row"), 3)
        self.assertIn("onReaderTouchStart", detail)
        self.assertIn("onReaderTouchEnd", detail)
        self.assertIn("height: 100dvh", detail)
        self.assertIn("grid-template-columns: var(--mobile-cover-width) minmax(0, 1fr)", detail)
        self.assertIn("Show all ${tags.length} tags", detail)
        self.assertIn(".manga-tag-chip:nth-child(n + 9)", detail)
        self.assertIn("reader-option-group flex flex-none", detail)
        self.assertIn("<TopBar />", danbooru_surface)
        self.assertIn("<MangaView />", manayomi_surface)
        self.assertNotIn("TopBar", manayomi_surface)

    def test_toolbar_alignment_language_badges_and_browse_reveal_contract(self) -> None:
        manga = ROOT / "frontend" / "src" / "components" / "manga"
        api = (manga / "mangaApi.ts").read_text(encoding="utf-8")
        library = (manga / "MangaLibrary.svelte").read_text(encoding="utf-8")
        browse = (manga / "MangaBrowse.svelte").read_text(encoding="utf-8")
        providers = (manga / "MangaBrowseProviders.svelte").read_text(encoding="utf-8")
        queries = (ROOT / "backend" / "manga" / "queries.py").read_text(encoding="utf-8")

        for name, code in (("japanese", "JP"), ("english", "EN"), ("chinese", "CN")):
            self.assertIn(f"{name}: '{code}'", api)
        self.assertIn('class="library-toolbar', library)
        self.assertLess(library.index('aria-label="Structured library filters"'), library.index('aria-label="Toggle Library categories and top tags"'))
        self.assertIn('aria-label="Manga languages"', library)
        self.assertIn('absolute bottom-1.5 right-1.5', library)
        self.assertNotIn('>Blacklisted</span>', library)
        self.assertIn("filter-button", providers)
        self.assertIn("bind:filterOpen", providers)
        self.assertNotIn('aria-label="Toggle Browse filters"', browse)
        self.assertIn("MangaFilterSheet", browse)
        self.assertIn('aria-label="Manga languages"', browse)
        self.assertIn('absolute bottom-1.5 right-1.5', browse)
        self.assertIn('>Blacklisted</span>', browse)
        self.assertIn("revealedIgnored = new Set(revealedIgnored).add(item.id)", browse)
        self.assertIn("openBrowseItem(item)", browse)
        self.assertIn("blacklist-cover-overlay.is-revealed", browse)
        self.assertIn("forceCoverVisible: ignored", browse)
        self.assertIn("AND NOT EXISTS", queries)
        self.assertIn("ignored_tags", queries)

    def test_cover_reading_progress_and_category_sort_contract(self) -> None:
        manga = ROOT / "frontend" / "src" / "components" / "manga"
        api = (manga / "mangaApi.ts").read_text(encoding="utf-8")
        library = (manga / "MangaLibrary.svelte").read_text(encoding="utf-8")
        view = (manga / "MangaView.svelte").read_text(encoding="utf-8")
        settings = (manga / "MangaSettings.svelte").read_text(encoding="utf-8")
        queries = (ROOT / "backend" / "manga" / "queries.py").read_text(encoding="utf-8")
        settings_py = (ROOT / "backend" / "manga" / "settings.py").read_text(encoding="utf-8")
        router = (ROOT / "backend" / "routers" / "manga.py").read_text(encoding="utf-8")

        # Read-progress travels on the card, is surfaced as a cover line, and is
        # configurable through the persisted cover_progress setting.
        for field in ("read_last_page", "read_page_count", "read_completed_at"):
            self.assertIn(field, api)
            self.assertIn(field, queries)
        self.assertIn("CoverProgressMode", api)
        self.assertIn("cover_progress", api)
        self.assertIn("progressInfo(card)", library)
        self.assertIn("width: {prog.percent}%", library)
        self.assertIn("{coverProgress}", view)
        self.assertIn("cover_progress: e.currentTarget.value", settings)
        self.assertIn("cover_progress", settings_py)
        self.assertIn("cover_progress: str | None = None", router)

        # "Recently added to category" is a category-scoped sort backed by the
        # membership timestamp; leaving the category drops back to the default.
        self.assertIn("Recently added to category", library)
        self.assertIn("sort === 'category_added'", library)
        self.assertIn("category_added", queries)
        self.assertIn("ci.added_at", queries)

    def test_series_grouping_contract(self) -> None:
        manga = ROOT / "frontend" / "src" / "components" / "manga"
        api = (manga / "mangaApi.ts").read_text(encoding="utf-8")
        library = (manga / "MangaLibrary.svelte").read_text(encoding="utf-8")
        detail = (manga / "MangaDetailOverlay.svelte").read_text(encoding="utf-8")
        database = (ROOT / "backend" / "manga" / "database.py").read_text(encoding="utf-8")
        queries = (ROOT / "backend" / "manga" / "queries.py").read_text(encoding="utf-8")
        router = (ROOT / "backend" / "routers" / "manga.py").read_text(encoding="utf-8")

        # Durable grouping lives in the user DB and is keyed like the rest of it.
        self.assertIn("CREATE TABLE IF NOT EXISTS series", database)
        self.assertIn("CREATE TABLE IF NOT EXISTS series_items", database)
        self.assertIn("SERIES_COLLAPSE_CLAUSE", queries)
        self.assertIn("def create_series", queries)
        self.assertIn("def series_detail", queries)
        self.assertIn("def set_series_first", queries)
        for field in ("series_id", "series_title", "series_chapter_count"):
            self.assertIn(field, api)
            self.assertIn(field, queries)

        # Every series endpoint is wired.
        for route in (
            '@router.get("/api/manga/series")',
            '@router.post("/api/manga/series")',
            '@router.get("/api/manga/series/{series_id}")',
            '@router.post("/api/manga/series/{series_id}/items")',
            '@router.delete("/api/manga/series/items/{gallery_id}")',
            '@router.post("/api/manga/series/items/{gallery_id}/first")',
        ):
            self.assertIn(route, router)

        # Library collapses to one card that expands inline into a chapter strip.
        self.assertIn("toggleSeries", library)
        self.assertIn("expandedSeries", library)
        self.assertIn("series-expanded", library)
        self.assertIn("series-strip", library)
        self.assertIn("mangaApi.seriesDetail", library)

        # The overlay is where a chapter is combined into a series.
        self.assertIn("createSeriesFromThis", detail)
        self.assertIn("addToExistingSeries", detail)
        self.assertIn("removeFromSeries", detail)
        self.assertIn("setSeriesFirst", detail)
        self.assertIn("New series name", detail)

    def test_downloads_heh_tags_history_resume_and_backdrop_contract(self) -> None:
        manga = ROOT / "frontend" / "src" / "components" / "manga"
        view = (manga / "MangaView.svelte").read_text(encoding="utf-8")
        menu = (manga / "MangaDownloadsMenu.svelte").read_text(encoding="utf-8")
        downloads = (manga / "MangaDownloads.svelte").read_text(encoding="utf-8")
        tags = (manga / "MangaTags.svelte").read_text(encoding="utf-8")
        history = (manga / "MangaHistory.svelte").read_text(encoding="utf-8")
        detail = (manga / "MangaDetailOverlay.svelte").read_text(encoding="utf-8")
        database = (ROOT / "backend" / "manga" / "database.py").read_text(encoding="utf-8")
        router = (ROOT / "backend" / "routers" / "manga.py").read_text(encoding="utf-8")

        self.assertIn("<MangaDownloadsMenu", view)
        self.assertIn("hidden sm:inline\">Downloads", view)
        self.assertIn("Show all", menu)
        self.assertIn("mangaApi.recentDownloads(5)", menu)
        self.assertIn("All downloaded manga", downloads)
        self.assertIn("['tags', 'Tags']", view)
        self.assertIn("['history', 'History']", view)
        self.assertIn("mangaApi.hehTags(sort)", tags)
        self.assertIn('placeholder="Find a downloaded tag"', tags)
        self.assertIn("visibleTags", tags)
        self.assertIn("column-count: 2", tags)
        self.assertIn("column-count: 4", tags)
        self.assertIn("column-count: 6", tags)
        self.assertIn("downloaded tags with exact Library counts", tags)
        self.assertNotIn("export let enabled", tags)
        self.assertNotIn("Counts come from HeH", tags)
        self.assertIn("Show all history", history)
        self.assertIn("startReading", history)
        self.assertIn("saveReadingProgress", detail)
        self.assertIn("onScrollReader", detail)
        self.assertIn('aria-label="Close manga information background"', detail)
        self.assertIn('tabindex="-1"', detail)
        self.assertIn("CREATE TABLE IF NOT EXISTS reading_history", database)
        self.assertIn('/api/manga/heh/tags', router)
        self.assertIn('/api/manga/downloads/recent', router)
        self.assertIn('/api/manga/history', router)


SCAN_SCRIPT = r"""
import json, sys, time, zipfile
from pathlib import Path

sys.path.insert(0, sys.argv[1])  # backend dir

root_dir = Path(sys.argv[2])
chapter = root_dir / "Test Title--m123" / "doujinshi - Chapter--c123"
chapter.mkdir(parents=True)

from PIL import Image
import io
buffer = io.BytesIO()
Image.new("RGB", (32, 48), (200, 60, 120)).save(buffer, "PNG")
with zipfile.ZipFile(chapter / "chapter.cbz", "w") as archive:
    archive.writestr("page_0.png", buffer.getvalue())

gallery = {
    "id": 123, "media_id": "999",
    "title": {"english": "Test Title EN", "pretty": "Test Title"},
    "cover": {"path": "galleries/999/cover.jpg", "width": 1, "height": 1},
    "upload_date": 1637172697, "num_pages": 1, "num_favorites": 5,
    "tags": [
        {"id": 1, "type": "tag", "name": "yuri", "count": 1},
        {"id": 2, "type": "language", "name": "english", "count": 1},
        {"id": 3, "type": "tag", "name": "personality", "count": 1},
        {"id": 4, "type": "tag", "name": "excretion", "count": 1},
        {"id": 5, "type": "tag", "name": "drunk", "count": 1},
        {"id": 6, "type": "tag", "name": "shared senses", "count": 1},
        {"id": 7, "type": "group", "name": "yuri", "count": 1},
    ],
    "pages": [],
}
(chapter / "nhentai.json").write_text(json.dumps(gallery), encoding="utf-8")

from manga.roots import add_root, get_root, preview_relocation, relocate_root
from manga.scanner import start_scan, scan_progress
from manga.queries import (
    create_category,
    file_path_for_gallery,
    get_manga_by_gallery_id,
    list_categories,
    reading_history,
    reading_progress,
    recent_downloads,
    save_reading_progress,
    search_library,
    downloaded_tag_directory,
    toggle_category_membership,
    toggle_favorite,
)
from manga.database import index_session, user_session
from manga.metadata import upsert_manga
from manga.search import parse_library_query

result = add_root(str(root_dir))
assert result["ok"], result
root_id = result["root"]["id"]

assert start_scan(root_id, enrich=False)
for _ in range(100):
    if not scan_progress()["running"]:
        break
    time.sleep(0.1)
progress = scan_progress()
assert progress["added"] == 1 and progress["matched"] == 1, progress

found = search_library(parse_library_query("yuri"), sort="recent")
assert found["total"] == 1, found["total"]
card = found["manga"][0]
assert card["gallery_id"] == 123 and card["favorite"] == 0
original_added_at = card["created_at"]
with user_session() as user:
    addition = user.execute(
        "SELECT added_at FROM library_additions WHERE source='nhentai' AND gallery_id=123"
    ).fetchone()
assert addition and addition["added_at"] == original_added_at, addition
recent = recent_downloads(limit=1)
assert recent["total"] == 1 and recent["manga"][0]["gallery_id"] == 123, recent
# The directory count comes from real manga/tag links, not the denormalized
# summary column, so a stale scan summary cannot lie to the UI.
with index_session() as index:
    index.execute("UPDATE tags SET manga_count=999 WHERE name='yuri' AND category='tag'")
downloaded_tags = downloaded_tag_directory(sort="a-z")
assert [item["name"] for item in downloaded_tags] == [
    "drunk", "excretion", "personality", "shared senses", "yuri"
], downloaded_tags
assert all(item["count"] == 1 for item in downloaded_tags), downloaded_tags
with index_session() as index:
    index.execute("UPDATE tags SET manga_count=1 WHERE name='yuri' AND category='tag'")

saved_progress = save_reading_progress(
    123,
    title="Test Title",
    cover_path=None,
    last_page=4,
    page_count=10,
)
assert saved_progress["last_page"] == 4 and saved_progress["completed_at"] is None, saved_progress
assert reading_progress(123)["last_page"] == 4
history = reading_history(limit=10)
assert history["total"] == 1 and history["items"][0]["local_manga_id"] == card["id"], history

# Read-progress rides along on Library cards so covers can draw a resume line.
progress_card = search_library(parse_library_query("yuri"), sort="recent")["manga"][0]
assert progress_card["read_last_page"] == 4 and progress_card["read_page_count"] == 10, progress_card
assert progress_card["read_completed_at"] is None, progress_card

# "Recently added to category" sorts galleries by when they joined the category.
create_category("Reading")
reading_category_id = [c for c in list_categories() if c["name"] == "Reading"][0]["id"]
assert toggle_category_membership(123, reading_category_id) is True
in_category = search_library(
    parse_library_query(""), sort="category_added", category_id=reading_category_id
)
assert in_category["total"] == 1 and in_category["manga"][0]["gallery_id"] == 123, in_category
with user_session() as user:
    membership = user.execute(
        "SELECT added_at FROM category_items WHERE category_id=? AND gallery_id=123",
        (reading_category_id,),
    ).fetchone()
assert membership and membership["added_at"] is not None, membership

# The disposable index can be rebuilt without replacing the precious first-added date.
with index_session() as index:
    manga_id = index.execute("SELECT id FROM manga WHERE gallery_id=123").fetchone()[0]
    index.execute("DELETE FROM manga_tags WHERE manga_id=?", (manga_id,))
    index.execute("DELETE FROM manga WHERE id=?", (manga_id,))
time.sleep(0.01)
upsert_manga(
    gallery_id=123,
    file_path=chapter / "chapter.cbz",
    root_id=root_id,
    cover_name="123.webp",
    file_size=(chapter / "chapter.cbz").stat().st_size,
    gallery=gallery,
)
rebuilt = get_manga_by_gallery_id(123)
assert rebuilt["created_at"] == original_added_at, rebuilt

assert toggle_favorite(123) is True
assert get_manga_by_gallery_id(123)["favorite"] == 1
hidden = search_library(
    parse_library_query(""), sort="recent", ignored_tags=["YURI"], show_ignored=False
)
assert hidden["total"] == 0, hidden
shown = search_library(
    parse_library_query(""), sort="recent", ignored_tags=["yuri"], show_ignored=True
)
assert shown["total"] == 1, shown

# Second scan is idempotent: everything skipped.
assert start_scan(root_id, enrich=False)
for _ in range(100):
    if not scan_progress()["running"]:
        break
    time.sleep(0.1)
progress = scan_progress()
assert progress["skipped"] == 1 and progress["added"] == 0, progress

# A moved library is rebased only after every indexed file is verified at the
# destination. User-owned favourites remain keyed to the gallery, not a path.
moved_root = root_dir.with_name(root_dir.name + "-moved")
root_dir.rename(moved_root)
preview = preview_relocation(root_id, str(moved_root))
assert preview["indexed_files"] == 1 and preview["verified_files"] == 1, preview
relocate_root(root_id, str(moved_root))
assert Path(get_root(root_id)["path"]) == moved_root.resolve()
relocated = get_manga_by_gallery_id(123)
assert Path(file_path_for_gallery(123)).is_file(), relocated
assert relocated["favorite"] == 1, relocated

# A Windows registration imported on Linux has the same verified relocation
# contract, and a failed preview must leave both stored paths unchanged.
import os
if os.name != "nt":
    from pathlib import PureWindowsPath
    from manga.database import index_session, user_session
    old_windows_root = PureWindowsPath("D:/previous-library")
    real_media = Path(file_path_for_gallery(123))
    old_windows_file = old_windows_root.joinpath(*real_media.relative_to(moved_root).parts)
    with user_session() as user:
        user.execute("UPDATE roots SET path=? WHERE id=?", (str(old_windows_root), root_id))
    with index_session() as index:
        index.execute("UPDATE manga SET file_path=? WHERE gallery_id=123", (str(old_windows_file),))
    missing_destination = moved_root.parent / "missing-destination"
    missing_destination.mkdir()
    try:
        preview_relocation(root_id, str(missing_destination))
    except ValueError:
        pass
    else:
        raise AssertionError("Missing media must prevent relocation")
    assert get_root(root_id)["path"] == str(old_windows_root)
    assert file_path_for_gallery(123) == str(old_windows_file)
    preview = preview_relocation(root_id, str(moved_root))
    assert preview["old_path"] == str(old_windows_root), preview
    relocate_root(root_id, str(moved_root))
    assert Path(file_path_for_gallery(123)) == real_media
    assert get_manga_by_gallery_id(123)["favorite"] == 1

print("SCAN_TEST_OK")
"""


DOWNLOADED_IDS_SCRIPT = r"""
import json
import socket
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from unittest.mock import patch
sys.path.insert(0, sys.argv[1])

import uvicorn
from manga import database, queries
from manga.database import index_session, user_session
from routers import manga as router
from server import app

app.dependency_overrides[router._require_enabled] = lambda: None
# Exercise actual loopback HTTP without requiring optional TestClient dependencies.
sock = socket.socket()
sock.bind(('127.0.0.1', 0))
port = sock.getsockname()[1]
server = uvicorn.Server(uvicorn.Config(app, lifespan='off', loop='asyncio', http='h11', ws='none', log_level='warning'))
thread = threading.Thread(target=lambda: server.run(sockets=[sock]), daemon=True)
thread.start()
deadline = time.monotonic() + 10
while not server.started:
    assert thread.is_alive() and time.monotonic() < deadline, 'Test server did not start'
    time.sleep(0.01)

class Client:
    def request(self, method, path, body=None):
        request = Request('http://127.0.0.1:' + str(port) + path, method=method,
                          data=json.dumps(body).encode() if body is not None else None,
                          headers={'Content-Type': 'application/json'})
        try:
            response = urlopen(request, timeout=10)
        except HTTPError as error:
            response = error
        with response:
            text = response.read().decode('utf-8')
            return SimpleNamespace(status_code=response.status, text=text, headers=response.headers,
                                   json=lambda: json.loads(text))

    def get(self, path):
        return self.request('GET', path)

    def post(self, path, json):
        return self.request('POST', path, json)

    def delete(self, path):
        return self.request('DELETE', path)

client = Client()
base = '/api/manga/downloaded-ids'
assert 'text/plain' in app.openapi()['paths'][base + '/export']['get']['responses']['200']['content']
assert client.get(base).json() == {'lists': []}
assert client.get(base + '/export').text == ''

media = Path(sys.argv[2]) / 'media.cbz'
media.write_bytes(b'preserved local archive')
with index_session() as index:
    for source, gallery_id in [('nhentai', 123456), ('nhentai', 42), ('mangadex', -1)]:
        index.execute(
            'INSERT INTO manga (source, gallery_id, file_path, title, created_at) VALUES (?, ?, ?, ?, ?)',
            (source, gallery_id, str(media) + str(gallery_id), 'Local manga', 1),
        )
with user_session() as user:
    user.execute("INSERT INTO favorites (source, gallery_id, created_at) VALUES ('nhentai', 123456, 1)")
    user.execute("INSERT INTO settings (key, value) VALUES ('blur_covers', '0')")

exported = client.get(base + '/export')
assert exported.status_code == 200
assert exported.text == '000042\n123456\n'
assert 'manayomi-downloaded-ids.txt' in exported.headers['content-disposition']
assert exported.headers['content-type'].startswith('text/plain')

first = client.post(base, json={'filename': 'PC library.txt', 'content': '\ufeff654321\r\n123456\r\n654321\r\n\n000042\n'})
assert first.status_code == 200, first.text
first_list = first.json()['lists'][0]
assert first_list['filename'] == 'PC library.txt' and first_list['count'] == 3
second = client.post(base, json={'filename': 'overlap.txt', 'content': '654321\n222222\n'})
assert second.status_code == 200
second_id = second.json()['lists'][1]['id']
assert queries.imported_downloaded_gallery_ids([42, 123456, 654321, 222222, 333333]) == {42, 123456, 654321, 222222}
assert queries.imported_downloaded_gallery_ids([]) == set()
assert queries.downloaded_gallery_ids([123456, 654321, 222222]) == {123456}
assert client.get(base + '/export').text == exported.text
assert client.get('/api/manga/settings').json()['blur_covers'] is False

for content in ('', ' \n', '654321\n12345\n', '1234567', '000000', '１２３４５６', '654321,222222', 'https://nhentai.net/g/654321/'):
    invalid = client.post(base, json={'filename': 'invalid.txt', 'content': content})
    assert invalid.status_code == 400, (content, invalid.text)
    assert client.get(base).json() == second.json()
assert client.post(base, json={'filename': 'bad\nname.txt', 'content': '654321'}).status_code == 400
assert client.post(base, json={'filename': 'x' * 256, 'content': '654321'}).status_code == 422
assert client.post(base, json={'filename': 'large.txt', 'content': ' ' * 8_000_001}).status_code == 422

# Browse caching retains provider data, but downloaded markers are reconciled on every request.
remote_items = [{'id': gid, 'tag_ids': []} for gid in [123456, 654321, 222222, 333333, 42]]
router._browse_cache.clear()
with (
    patch.object(router, '_nh_guard'),
    patch.object(router.nhentai, 'browse_galleries', return_value={'items': remote_items, 'num_pages': 1}) as remote,
):
    result = client.get('/api/manga/browse?per_page=20')
    assert result.status_code == 200, result.text
    items = result.json()['items']
    assert [item['id'] for item in items if item['downloaded']] == [123456, 42]
    assert [item['id'] for item in items if item['downloaded_elsewhere']] == [123456, 654321, 222222, 42]
    visible = [item['id'] for item in items if not item['downloaded'] and not item['downloaded_elsewhere']]
    assert visible == [333333]

    removed = client.delete(base + '/' + str(first_list['id']))
    assert removed.status_code == 200 and removed.json()['lists'] == [second.json()['lists'][1]]
    assert queries.imported_downloaded_gallery_ids([42, 123456, 654321, 222222]) == {654321, 222222}
    assert client.get(base + '/export').text == exported.text
    client.delete(base + '/' + str(second_id))
    items = client.get('/api/manga/browse?per_page=20').json()['items']
    assert not any(item['downloaded_elsewhere'] for item in items)
    assert [item['id'] for item in items if item['downloaded']] == [123456, 42]
    assert remote.call_count == 1
assert client.delete(base + '/' + str(second_id)).status_code == 404

roundtrip = client.post(base, json={'filename': 'export.txt', 'content': exported.text})
assert roundtrip.status_code == 200 and roundtrip.json()['lists'][0]['count'] == 2
# Reinitialization and index rebuild preserve the user-state list and organization.
database._initialized = False
assert client.get(base).json() == roundtrip.json()
with index_session() as index:
    index.execute('DELETE FROM manga')
assert client.get(base + '/export').text == ''
assert queries.imported_downloaded_gallery_ids([42, 123456]) == {42, 123456}
with user_session() as user:
    assert user.execute('SELECT COUNT(*) FROM favorites').fetchone()[0] == 1
assert media.read_bytes() == b'preserved local archive'
with patch.object(router, '_nh_guard'), patch.object(router.nhentai, 'get_gallery', return_value={'id': 123456, 'pages': []}):
    gallery = client.get('/api/manga/gallery/123456').json()
    assert gallery['downloaded'] is False and 'local_manga_id' not in gallery

app.dependency_overrides.clear()
with patch.object(router.suite_modules, 'enabled_ids', return_value={'files'}):
    assert client.get(base).status_code == 409
    assert client.get(base + '/export').status_code == 409
    assert client.post(base, json={'filename': 'x.txt', 'content': '123456'}).status_code == 409
    assert client.delete(base + '/1').status_code == 409
server.should_exit = True
thread.join(5)
assert not thread.is_alive()
print('DOWNLOADED_IDS_TEST_OK')
"""


class MangaDownloadedIdsIntegrationTests(unittest.TestCase):
    def test_import_export_overlap_removal_persistence_and_browse(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            completed = subprocess.run(
                [sys.executable, "-c", DOWNLOADED_IDS_SCRIPT, str(BACKEND), temporary],
                capture_output=True,
                text=True,
                timeout=60,
                env={**os.environ, "KEIVOTOS_HOME": str(Path(temporary) / "home")},
            )
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            self.assertIn("DOWNLOADED_IDS_TEST_OK", completed.stdout)


class MangaScanIntegrationTests(unittest.TestCase):
    def test_isolated_scan_index_search_and_favorite(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary) / "home"
            library = Path(temporary) / "library"
            library.mkdir()
            completed = subprocess.run(
                [sys.executable, "-c", SCAN_SCRIPT, str(BACKEND), str(library)],
                capture_output=True,
                text=True,
                timeout=120,
                env={**os.environ, "KEIVOTOS_HOME": str(home)},
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertIn("SCAN_TEST_OK", completed.stdout)


SERIES_SCRIPT = r"""
import sys
sys.path.insert(0, sys.argv[1])  # backend dir

from manga.database import index_session
from manga.queries import (
    add_to_series,
    create_series,
    delete_series,
    get_manga_by_gallery_id,
    list_series,
    remove_from_series,
    rename_series,
    reorder_series,
    search_library,
    series_detail,
    set_series_first,
)
from manga.search import parse_library_query

with index_session() as index:
    for gallery_id, title, created in ((123, "Work Ch.1", 10), (124, "Work Ch.2", 20), (200, "Standalone", 30)):
        index.execute(
            "INSERT INTO manga (source, gallery_id, file_path, title, created_at, matched)"
            " VALUES ('nhentai', ?, ?, ?, ?, 1)",
            (gallery_id, "/lib/%d.cbz" % gallery_id, title, created),
        )

assert search_library(parse_library_query(""))["total"] == 3

created = create_series("My Work", [123, 124])
assert created["ok"], created
series_id = created["series_id"]

# The series collapses to a single card (its first chapter), beside the standalone.
collapsed = search_library(parse_library_query(""))
assert collapsed["total"] == 2, collapsed
representative = [card for card in collapsed["manga"] if card["series_id"] == series_id]
assert len(representative) == 1 and representative[0]["gallery_id"] == 123, representative
assert representative[0]["series_title"] == "My Work", representative[0]
assert representative[0]["series_chapter_count"] == 2, representative[0]
standalone = [card for card in collapsed["manga"] if card["gallery_id"] == 200][0]
assert standalone["series_id"] is None, standalone

assert [chapter["gallery_id"] for chapter in series_detail(series_id)["chapters"]] == [123, 124]

# "Set as first" changes which cover represents the series in the grid.
set_series_first(124)
regrouped = search_library(parse_library_query(""))
new_rep = [card for card in regrouped["manga"] if card["series_id"] == series_id][0]
assert new_rep["gallery_id"] == 124, new_rep
assert [chapter["gallery_id"] for chapter in series_detail(series_id)["chapters"]] == [124, 123]

reorder_series(series_id, [123, 124])
assert [chapter["gallery_id"] for chapter in series_detail(series_id)["chapters"]] == [123, 124]

rename_series(series_id, "Renamed Work")
assert list_series()[0]["title"] == "Renamed Work", list_series()

# Removing a chapter frees it; the series survives on its remaining chapter.
remove_from_series(124)
assert get_manga_by_gallery_id(124)["series_id"] is None
assert [chapter["gallery_id"] for chapter in series_detail(series_id)["chapters"]] == [123]

# Removing the final chapter prunes the now-empty series.
remove_from_series(123)
assert list_series() == [], list_series()
assert series_detail(series_id) is None

assert add_to_series(9999, 123)["ok"] is False

print("SERIES_TEST_OK")
"""


class MangaSeriesIntegrationTests(unittest.TestCase):
    def test_series_grouping_collapse_and_ordering(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary) / "home"
            completed = subprocess.run(
                [sys.executable, "-c", SERIES_SCRIPT, str(BACKEND)],
                capture_output=True,
                text=True,
                timeout=120,
                env={**os.environ, "KEIVOTOS_HOME": str(home)},
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertIn("SERIES_TEST_OK", completed.stdout)


BROWSER_SCRIPT = r"""
const assert = require('node:assert/strict');
const config = JSON.parse(process.argv[2]);
const { chromium } = require(config.playwrightModule);
const { expect } = require(config.playwrightModule + '/test');
const origin = new URL(config.url).origin;
const mode = process.argv[1];
const card = {
  id: 101, source: 'nhentai', gallery_id: 123456, title: 'Filter regression manga',
  pages: 1, created_at: 1, languages: 'english', favorite: 0, pinned: 0,
  series_id: null, read_last_page: null, read_page_count: null
};
const tags = [
  { category: 'tag', name: 'original tag' }, { category: 'artist', name: 'fixture artist' }
];
const dex = {
  id: '11111111-1111-4111-8111-111111111111', title: 'Header regression MangaDex',
  description: '', authors: [], artists: [], cover_filename: '', tags: [],
  status: 'completed', year: 2020, original_language: 'ja', available_languages: ['en'],
  content_rating: 'safe', publication_demographic: '', links: {}, official_links: [],
  alternate_titles: [], downloaded_chapters: 0
};
const fixtures = {
  '/api/manga/settings': { nhentai_enabled: true, cf_clearance: '', user_agent: '',
    request_delay_ms: 1200, blur_covers: false, show_ignored: true, ignored_tags: [], cover_progress: 'bar' },
  '/api/manga/status': { suite: 'Keivotos', module: 'Manayomi', version: 'V1.1.2',
    manga_count: 1, tag_count: 2, nhentai_enabled: true, module_home: '', default_library: '' },
  '/api/manga/library': { manga: [card], total: 1, page: 1, per_page: 20, page_count: 1,
    stats: { manga_count: 1, tag_count: 2, favorite_count: 0 } },
  '/api/manga/detail/101': { ...card, tags, category_ids: [], files_source_id: null,
    files_relative_path: null, file_path: '/fixture/manga.cbz', root_id: null },
  '/api/manga/pages/123456': { gallery_id: 123456, pages: 1, names: ['page_0.png'], version: 'fixture' },
  '/api/manga/history/progress/123456': { progress: null },
  '/api/manga/categories': { categories: [] }, '/api/manga/series': { series: [] },
  '/api/manga/tags/top': { tags: [] }, '/api/manga/roots': { roots: [] },
  '/api/manga/downloaded-ids': { lists: [] },
  '/api/manga/history': { items: [], total: 0, limit: 200, offset: 0 },
  '/api/manga/scan': { running: false, root_id: null, total: 0, processed: 0, errors: [] },
  '/api/manga/enrich': { running: false, message: '', unmatched: 0, processed: 0, total: 0 },
  '/api/manga/migrate': { running: false, message: '', processed: 0, total: 0 },
  '/api/manga/browse': { items: [], page: 1, num_pages: 1, total: 0 },
  '/api/manga/downloads': { running: false, current: null, queue: [], recent: [] },
  '/api/manga/remote/mangadex/browse': { items: [dex], page: 1, num_pages: 1, total: 1 },
  [`/api/manga/remote/mangadex/title/${dex.id}`]: dex,
  [`/api/manga/remote/mangadex/title/${dex.id}/chapters`]: { items: [], total: 0 }
};
(async () => {
  const browser = await chromium.launch({ headless: true,
    ...(config.executable ? { executablePath: config.executable } : {}) });
  try {
    for (const viewport of [{ width: 1280, height: 900 }, { width: 390, height: 844 }]) {
      const context = await browser.newContext({ viewport });
      const page = await context.newPage();
      const errors = [];
      page.on('pageerror', error => errors.push(error.message));
      page.on('console', message => { if (message.type() === 'error') errors.push(message.text()); });
      page.on('response', response => { if (response.status() >= 400) errors.push(`${response.status()} ${response.url()}`); });
      await context.addInitScript(() => {
        localStorage.setItem('keivotos:active-module', JSON.stringify('manayomi'));
      });
      // Serve manga fixtures in the browser; reject mutations and external requests.
      await context.route('**/*', async route => {
        const request = route.request();
        const url = new URL(request.url());
        if (url.origin !== origin || request.method() !== 'GET') {
          errors.push(`Unexpected request: ${request.method()} ${request.url()}`);
          return route.abort();
        }
        if (url.pathname.startsWith('/api/manga/cover/')) return route.fulfill({
          contentType: 'image/svg+xml', body: '<svg xmlns="http://www.w3.org/2000/svg" width="140" height="200"><rect width="140" height="200" fill="#7065a0"/></svg>'
        });
        if (url.pathname in fixtures) return route.fulfill({ json: fixtures[url.pathname] });
        if (url.pathname.startsWith('/api/manga/')) {
          errors.push(`Missing fixture: ${url.pathname}`);
          return route.fulfill({ status: 500, json: { detail: 'Missing browser fixture' } });
        }
        return route.continue();
      });
      await page.goto(origin, { waitUntil: 'networkidle' });
      const libraryButton = page.getByRole('button', { name: 'Library', exact: true });
      const filterButton = page.getByRole('button', { name: 'Structured library filters', exact: true });
      const filter = page.getByRole('dialog', { name: 'Library filters', exact: true });
      const openLocal = () => page.getByRole('button', { name: /Filter regression manga/ }).click();
      const queryAfter = async (action, query) => {
        const response = page.waitForResponse(response => {
          const url = new URL(response.url());
          return url.pathname === '/api/manga/library' && (url.searchParams.get('q') ?? '') === query;
        });
        await action();
        await response;
      };
      const roundtrip = async section => {
        await page.getByRole('button', { name: section, exact: true }).click();
        await libraryButton.click();
        await filterButton.click();
        await page.waitForTimeout(220); // Allow the protected 180ms popover animation to finish.
      };
      await openLocal();
      if (mode === 'filters') {
        await queryAfter(() => page.locator('.manga-tag-chip').getByText('original tag', { exact: true }).click(), 'tag:"original tag"');
        await expect(filter.getByLabel('Tags', { exact: true })).toHaveValue('original tag');
        await filter.getByLabel('Tags', { exact: true }).fill('replacement tag, second tag');
        await filter.getByLabel('Artists', { exact: true }).fill('replacement artist');
        const editedQuery = 'tag:"replacement tag" tag:"second tag" artist:"replacement artist"';
        await queryAfter(() => filter.getByRole('button', { name: 'Apply', exact: true }).click(), editedQuery);
        await roundtrip('History');
        await expect(filter.getByLabel('Tags', { exact: true })).toHaveValue('replacement tag, second tag');
        await expect(filter.getByLabel('Artists', { exact: true })).toHaveValue('replacement artist');
        await queryAfter(() => filter.getByRole('button', { name: 'Apply', exact: true }).click(), editedQuery);
        await roundtrip('Settings');
        await expect(filter.getByLabel('Tags', { exact: true })).toHaveValue('replacement tag, second tag');
        await queryAfter(() => filter.getByRole('button', { name: 'Clear', exact: true }).click(), '');
        if (await filterButton.getAttribute('aria-expanded') === 'true') {
          await filter.getByRole('button', { name: 'Close Library filters', exact: true }).click();
        }
        await roundtrip('History');
        await expect(filter.getByLabel('Tags', { exact: true })).toHaveValue('');
        await expect(filter.getByLabel('Artists', { exact: true })).toHaveValue('');
        await filter.getByRole('button', { name: 'Close Library filters', exact: true }).click();
        // A fresh click, including the same tag, must still seed and open the filter.
        await openLocal();
        await queryAfter(() => page.locator('.manga-tag-chip').getByText('original tag', { exact: true }).click(), 'tag:"original tag"');
        await expect(filter.getByLabel('Tags', { exact: true })).toHaveValue('original tag');
        await filter.getByRole('button', { name: 'Close Library filters', exact: true }).click();
        await openLocal();
        await queryAfter(() => page.locator('.manga-tag-chip').getByText('fixture artist', { exact: true }).click(), 'tag:"original tag" artist:"fixture artist"');
        await expect(filter.getByLabel('Artists', { exact: true })).toHaveValue('fixture artist');
      } else {
        const verifyHeader = async (selector, closeName) => {
          const panel = page.locator(selector);
          const title = panel.locator('h2').first();
          const close = panel.getByRole('button', { name: closeName, exact: true });
          await expect(title).toBeVisible();
          const titleBox = await title.boundingBox();
          const closeBox = await close.boundingBox();
          assert(closeBox.x + closeBox.width < titleBox.x, 'Close button must be left of the title');
          assert(titleBox.x + titleBox.width <= viewport.width, 'Title must stay within the viewport');
          await close.click();
          await expect(panel).toHaveCount(0);
        };
        await verifyHeader('.manga-info-panel', 'Close manga information');
        await openLocal();
        await page.keyboard.press('Escape');
        await expect(page.locator('.manga-info-panel')).toHaveCount(0);
        await openLocal();
        await page.getByRole('button', { name: 'Close manga information background', exact: true }).click({ position: { x: 2, y: 2 } });
        await expect(page.locator('.manga-info-panel')).toHaveCount(0);
        await page.getByRole('button', { name: 'Browse', exact: true }).click();
        await page.getByRole('tab', { name: 'MangaDex', exact: true }).click();
        await page.getByRole('button', { name: /Header regression MangaDex/ }).click();
        await verifyHeader('.md-detail', 'Close MangaDex information');
        await page.getByRole('button', { name: /Header regression MangaDex/ }).click();
        await page.keyboard.press('Escape');
        await expect(page.locator('.md-detail')).toHaveCount(0);
        await page.getByRole('button', { name: /Header regression MangaDex/ }).click();
        await page.getByRole('button', { name: 'Close MangaDex information background', exact: true }).click({ position: { x: 2, y: 2 } });
        await expect(page.locator('.md-detail')).toHaveCount(0);
      }
      assert.deepEqual(errors, [], 'Browser console/runtime/request errors');
      console.log(`${mode.toUpperCase()}_BROWSER_OK ${viewport.width}x${viewport.height}`);
      await context.close();
    }
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
"""


@unittest.skipUnless(
    os.environ.get("MANAYOMI_BROWSER_URL") and os.environ.get("MANAYOMI_PLAYWRIGHT_MODULE"),
    "Set MANAYOMI_BROWSER_URL and MANAYOMI_PLAYWRIGHT_MODULE for timed browser checks",
)
class MangaBrowserRegressionTests(unittest.TestCase):
    """Run against a built app with Manayomi enabled; manga APIs are fixture-only.

    MANAYOMI_BROWSER_NODE selects Node (default: node), and optional
    MANAYOMI_BROWSER_EXECUTABLE selects an installed Chromium/Edge executable.
    No browser installation, media transfer, or server mutation is performed.
    """

    def run_browser(self, mode: str) -> None:
        config = json.dumps({
            "url": os.environ["MANAYOMI_BROWSER_URL"],
            "playwrightModule": os.environ["MANAYOMI_PLAYWRIGHT_MODULE"],
            "executable": os.environ.get("MANAYOMI_BROWSER_EXECUTABLE"),
        })
        completed = subprocess.run(
            [os.environ.get("MANAYOMI_BROWSER_NODE", "node"), "-e", BROWSER_SCRIPT, mode, config],
            capture_output=True, text=True, timeout=90,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        for size in ("1280x900", "390x844"):
            self.assertIn(f"{mode.upper()}_BROWSER_OK {size}", completed.stdout)

    def test_library_filter_edits_and_clears_survive_remounts(self) -> None:
        self.run_browser("filters")

    def test_information_close_buttons_precede_titles(self) -> None:
        self.run_browser("headers")


if __name__ == "__main__":
    unittest.main()
