"""Writable locations for the Manayomi manga module.

Everything lives beneath the suite home (``Data/`` in this combined project),
mirroring the Danbooru module layout: ``Data/modules/manga/``.
"""
from __future__ import annotations

from config import MODULE_REGISTRY, SUITE_HOME

MANGA_MODULE_SLUG = "manayomi"
MANGA_DESCRIPTOR = MODULE_REGISTRY.require(MANGA_MODULE_SLUG)
MANGA_MODULE_HOME = MANGA_DESCRIPTOR.home
MANGA_INDEX_DB_PATH = MANGA_DESCRIPTOR.database
MANGA_USER_DB_PATH = MANGA_MODULE_HOME / "user.sqlite"
MANGA_COVERS_DIR = MANGA_MODULE_HOME / "covers"
MANGA_BACKUP_DIR = SUITE_HOME / "backups" / "manga"


def ensure_module_dirs() -> None:
    MANGA_MODULE_HOME.mkdir(parents=True, exist_ok=True)
    MANGA_COVERS_DIR.mkdir(parents=True, exist_ok=True)
