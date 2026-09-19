"""Manga module settings, stored in the module user database.

Online nHentai access is opt-in (decision 2026-07-19): browsing and downloads
stay disabled until the user enables them in Settings. Cloudflare fields
(cf_clearance + matching User-Agent) are optional fallbacks for when nHentai
challenges the connection.
"""
from __future__ import annotations

import json
from typing import Any

from manga.database import get_setting, set_setting

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
DEFAULT_REQUEST_DELAY_MS = 1000
MIN_REQUEST_DELAY_MS = 250
MAX_REQUEST_DELAY_MS = 10000

# How the read-progress indicator on Library covers is rendered.
COVER_PROGRESS_MODES = ("off", "bar", "percent", "pages")
DEFAULT_COVER_PROGRESS = "bar"


def _bounded_delay(value: Any) -> int:
    try:
        parsed = int(round(float(value)))
    except (TypeError, ValueError, OverflowError):
        return DEFAULT_REQUEST_DELAY_MS
    return max(MIN_REQUEST_DELAY_MS, min(MAX_REQUEST_DELAY_MS, parsed))


def _flag(key: str, default: bool) -> bool:
    raw = get_setting(key)
    if raw is None:
        return default
    return raw == "1"


def get_manga_settings() -> dict[str, Any]:
    """Effective module settings for the API/UI."""
    raw_tags = get_setting("ignored_tags", "[]") or "[]"
    try:
        ignored = [tag for tag in json.loads(raw_tags) if isinstance(tag, str)]
    except json.JSONDecodeError:
        ignored = []
    return {
        "nhentai_enabled": _flag("nh_enabled", False),
        "cf_clearance": get_setting("nh_cf_clearance", "") or "",
        "user_agent": get_setting("nh_user_agent", "") or DEFAULT_USER_AGENT,
        "request_delay_ms": _bounded_delay(get_setting("nh_request_delay_ms", str(DEFAULT_REQUEST_DELAY_MS))),
        "blur_covers": _flag("blur_covers", True),
        "show_ignored": _flag("show_ignored", True),
        "cover_progress": _cover_progress(),
        "ignored_tags": ignored,
    }


def _cover_progress() -> str:
    value = (get_setting("cover_progress") or DEFAULT_COVER_PROGRESS).strip().lower()
    return value if value in COVER_PROGRESS_MODES else DEFAULT_COVER_PROGRESS


def update_manga_settings(changes: dict[str, Any]) -> dict[str, Any]:
    """Persist a partial settings update; unknown keys are ignored."""
    if "nhentai_enabled" in changes:
        set_setting("nh_enabled", "1" if changes["nhentai_enabled"] else "0")
    if "cf_clearance" in changes:
        set_setting("nh_cf_clearance", str(changes["cf_clearance"] or "").strip())
    if "user_agent" in changes:
        set_setting("nh_user_agent", str(changes["user_agent"] or "").strip() or DEFAULT_USER_AGENT)
    if "request_delay_ms" in changes:
        set_setting("nh_request_delay_ms", str(_bounded_delay(changes["request_delay_ms"])))
    if "blur_covers" in changes:
        set_setting("blur_covers", "1" if changes["blur_covers"] else "0")
    if "show_ignored" in changes:
        set_setting("show_ignored", "1" if changes["show_ignored"] else "0")
    if "cover_progress" in changes:
        mode = str(changes["cover_progress"] or "").strip().lower()
        set_setting("cover_progress", mode if mode in COVER_PROGRESS_MODES else DEFAULT_COVER_PROGRESS)
    if "ignored_tags" in changes and isinstance(changes["ignored_tags"], list):
        cleaned = sorted(
            {
                str(tag).strip().lower()
                for tag in changes["ignored_tags"]
                if isinstance(tag, str) and str(tag).strip()
            }
        )
        set_setting("ignored_tags", json.dumps(cleaned, ensure_ascii=False))
    return get_manga_settings()


def nhentai_enabled() -> bool:
    return _flag("nh_enabled", False)
