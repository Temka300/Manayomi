from __future__ import annotations

import sys
import sqlite3
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from module_registry import build_registry  # noqa: E402
from files_base import sources  # noqa: E402


class ModuleRegistryTests(unittest.TestCase):
    def test_static_registry_has_one_required_base_and_danbooru_module(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as temporary:
            home = Path(temporary)
            registry = build_registry(home, "1.1.0")

        files = registry.require("files")
        danbooru = registry.require("danbooru")
        self.assertEqual(registry.base, files)
        self.assertTrue(files.is_base)
        self.assertFalse(files.disableable)
        self.assertEqual(files.database, home.resolve() / "base" / "files.sqlite")
        self.assertEqual(files.api_prefix, "/api/files")
        self.assertFalse(danbooru.is_base)
        self.assertTrue(danbooru.disableable)
        self.assertEqual(danbooru.database, home.resolve() / "modules" / "danbooru" / "danbooru.sqlite")
        self.assertEqual(danbooru.api_prefix, "/api/danbooru")
        self.assertIn("Danbooru", danbooru.user_agent)
        reddit = registry.require("reddit")
        self.assertEqual(
            reddit.browsable_roots,
            (home.resolve() / "modules" / "reddit" / "media" / "library",),
        )
        karaoke = registry.require("karaoke")
        self.assertEqual(karaoke.api_prefix, "/api/karaoke")
        self.assertEqual(
            karaoke.browsable_roots,
            (home.resolve() / "modules" / "karaoke" / "media" / "library",),
        )
        youtube = registry.require("youtube")
        self.assertEqual(youtube.api_prefix, "/api/youtube")
        self.assertEqual(
            youtube.browsable_roots,
            (home.resolve() / "modules" / "youtube" / "media" / "library",),
        )
        language = registry.require("language")
        self.assertEqual(language.api_prefix, "/api/language")
        self.assertEqual(
            language.browsable_roots,
            (home.resolve() / "modules" / "language" / "media" / "library",),
        )
        self.assertEqual(
            language.credentials,
            home.resolve() / "modules" / "language" / "language_credentials.json",
        )
        manayomi = registry.require("manayomi")
        self.assertEqual(manayomi.name, "Manayomi")
        self.assertEqual(manayomi.home, home.resolve() / "modules" / "manga")
        self.assertEqual(manayomi.database, home.resolve() / "modules" / "manga" / "manga.sqlite")
        self.assertEqual(manayomi.api_prefix, "/api/manga")
        self.assertTrue(manayomi.disableable)
        self.assertEqual(len(tuple(registry)), 7)

    def test_reddit_publishes_existing_download_library_to_files(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as temporary:
            home = Path(temporary).resolve()
            registry = build_registry(home, "1.1.0")
            reddit = registry.require("reddit")
            reddit.browsable_roots[0].mkdir(parents=True)
            connection = sqlite3.connect(":memory:")
            connection.row_factory = sqlite3.Row
            reddit.publish(connection)
            published = sources.list_sources(connection)
            connection.close()

        self.assertEqual(len(published), 1)
        self.assertEqual(published[0].role, "reddit")
        self.assertEqual(published[0].display_name, "Reddit downloads")

    def test_karaoke_publishes_existing_library_to_files(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as temporary:
            home = Path(temporary).resolve()
            registry = build_registry(home, "1.1.0")
            karaoke = registry.require("karaoke")
            karaoke.browsable_roots[0].mkdir(parents=True)
            connection = sqlite3.connect(":memory:")
            connection.row_factory = sqlite3.Row
            karaoke.publish(connection)
            published = sources.list_sources(connection)
            connection.close()

        self.assertEqual(len(published), 1)
        self.assertEqual(published[0].role, "karaoke")
        self.assertEqual(published[0].display_name, "Karaoke library")

    def test_youtube_publishes_existing_library_to_files(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as temporary:
            home = Path(temporary).resolve()
            registry = build_registry(home, "1.1.0")
            youtube = registry.require("youtube")
            youtube.browsable_roots[0].mkdir(parents=True)
            connection = sqlite3.connect(":memory:")
            connection.row_factory = sqlite3.Row
            youtube.publish(connection)
            published = sources.list_sources(connection)
            connection.close()

        self.assertEqual(len(published), 1)
        self.assertEqual(published[0].role, "youtube")
        self.assertEqual(published[0].display_name, "YouTube downloads")

    def test_language_initializes_and_publishes_its_library_to_files(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as temporary:
            home = Path(temporary).resolve()
            registry = build_registry(home, "1.1.0")
            language = registry.require("language")
            connection = sqlite3.connect(":memory:")
            connection.row_factory = sqlite3.Row
            language.publish(connection)
            published = sources.list_sources(connection)
            connection.close()

        self.assertEqual(len(published), 1)
        self.assertEqual(published[0].role, "language")
        self.assertEqual(published[0].display_name, "Languages media")

    def test_registry_rejects_duplicate_slugs(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as temporary:
            registry = build_registry(Path(temporary), "1.1.0")
        with self.assertRaises(ValueError):
            type(registry)((registry.base, registry.base))


if __name__ == "__main__":
    unittest.main()
