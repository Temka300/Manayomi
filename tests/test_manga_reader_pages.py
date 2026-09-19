"""Regression coverage for Library page sizing and read-only CBZ delivery."""
from __future__ import annotations

import io
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from manga import reader_pages  # noqa: E402
from manga.queries import normalize_page_size  # noqa: E402
from manga.reader_pages import archive_pages, clear_reader_caches, read_page  # noqa: E402


def image_bytes(size: tuple[int, int], color: tuple[int, int, int]) -> bytes:
    output = io.BytesIO()
    Image.new("RGB", size, color).save(output, "PNG")
    return output.getvalue()


class MangaPageSizeTests(unittest.TestCase):
    def test_zero_means_all_and_regular_sizes_remain_bounded(self) -> None:
        self.assertEqual(normalize_page_size(0, 537), 537)
        self.assertEqual(normalize_page_size(0, 0), 1)
        self.assertEqual(normalize_page_size(50, 537), 50)
        self.assertEqual(normalize_page_size(999, 537), 200)


class MangaReaderPageTests(unittest.TestCase):
    def setUp(self) -> None:
        clear_reader_caches()

    def tearDown(self) -> None:
        clear_reader_caches()

    def test_page_list_is_cached_and_versioned_by_archive_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            archive = Path(temporary) / "chapter.cbz"
            with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_STORED) as cbz:
                cbz.writestr("page_10.png", image_bytes((40, 80), (10, 20, 30)))
                cbz.writestr("page_2.png", image_bytes((40, 80), (30, 20, 10)))

            with patch("manga.reader_pages.list_images", wraps=reader_pages.list_images) as listing:
                version, names = archive_pages(archive)
                self.assertEqual(names, ("page_2.png", "page_10.png"))
                self.assertEqual(archive_pages(archive), (version, names))
                self.assertEqual(listing.call_count, 1)

            with zipfile.ZipFile(archive, "a", compression=zipfile.ZIP_STORED) as cbz:
                cbz.writestr("page_11.png", image_bytes((40, 80), (40, 50, 60)))
            next_version, next_names = archive_pages(archive)
            self.assertNotEqual(next_version, version)
            self.assertEqual(len(next_names), 3)

    def test_fast_page_is_phone_sized_webp_and_memory_cached(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            archive = Path(temporary) / "chapter.cbz"
            original = image_bytes((2400, 3600), (90, 40, 160))
            with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_STORED) as cbz:
                cbz.writestr("page_1.png", original)

            with patch("manga.reader_pages._fast_webp", wraps=reader_pages._fast_webp) as encoder:
                fast, media_type, version, name = read_page(archive, 0, max_width=1600)
                repeated = read_page(archive, 0, max_width=1600)
                self.assertEqual(encoder.call_count, 1)

            self.assertEqual(media_type, "image/webp")
            self.assertEqual(name, "page_1.png")
            self.assertEqual(repeated, (fast, media_type, version, name))
            with Image.open(io.BytesIO(fast)) as image:
                self.assertEqual(image.width, 1600)
                self.assertEqual(image.height, 2400)

            source, source_type, source_version, _ = read_page(archive, 0)
            self.assertEqual(source, original)
            self.assertEqual(source_type, "image/png")
            self.assertEqual(source_version, version)

    def test_fast_page_preserves_an_already_phone_sized_source(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            archive = Path(temporary) / "chapter.cbz"
            original = image_bytes((1280, 1800), (30, 80, 140))
            with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_STORED) as cbz:
                cbz.writestr("page_1.png", original)

            with patch("manga.reader_pages._fast_webp", wraps=reader_pages._fast_webp) as encoder:
                fast, media_type, _, _ = read_page(archive, 0, max_width=1600)

            self.assertEqual(encoder.call_count, 0)
            self.assertEqual(fast, original)
            self.assertEqual(media_type, "image/png")


if __name__ == "__main__":
    unittest.main()
