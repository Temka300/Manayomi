"""nHentai v2 API client, ported from Waifu-Manga-Hoarder's nhentai.ts.

Sync (requests-based) because FastAPI runs plain-`def` endpoints in its thread
pool. All calls respect the user's request-delay throttle, retry politely on
429 (honoring ``Retry-After``), and fall back across CDN mirrors for images.

Online access is opt-in: callers must check ``settings.nhentai_enabled()``
before invoking anything here (``require_enabled`` does it for routers).
"""
from __future__ import annotations

import re
import threading
import time
from html.parser import HTMLParser
from typing import Any
from urllib.parse import unquote, urlparse

import requests

from manga.settings import get_manga_settings, nhentai_enabled

API = "https://nhentai.net"

RATE_LIMIT_RETRIES = 4
IMAGE_RATE_LIMIT_RETRIES = 2
MIN_RATE_LIMIT_BACKOFF_MS = 5000
CDN_TTL_SECONDS = 10 * 60
TAG_DIRECTORY_TTL_SECONDS = 15 * 60

SORT_TO_V2 = {
    "recent": "date",
    "popular": "popular",
    "popular-month": "popular-month",
    "popular-week": "popular-week",
    "popular-today": "popular-today",
}


class NhError(Exception):
    """An nHentai request failed; ``status`` carries the HTTP-ish code."""

    def __init__(self, message: str, status: int = 0):
        super().__init__(message)
        self.status = status


class NhDisabledError(NhError):
    """Online nHentai access is switched off in Settings."""

    def __init__(self) -> None:
        super().__init__(
            "Online nHentai access is disabled. Enable it in Settings first.", 403
        )


def require_enabled() -> None:
    if not nhentai_enabled():
        raise NhDisabledError()


_session = requests.Session()

_throttle_lock = threading.Lock()
_next_request_at = 0.0

_cdn_lock = threading.Lock()
_cdn_cache: dict[str, Any] | None = None
_cdn_cached_at = 0.0

_tag_directory_lock = threading.Lock()
_tag_directory_cache: list[dict[str, Any]] | None = None
_tag_directory_cached_at = 0.0


def _wait_for_request_turn() -> None:
    global _next_request_at
    delay_seconds = get_manga_settings()["request_delay_ms"] / 1000.0
    while True:
        with _throttle_lock:
            now = time.monotonic()
            if now >= _next_request_at:
                _next_request_at = now + delay_seconds
                return
            wait = _next_request_at - now
        time.sleep(min(wait, 1.0))


def _hold_requests_for(seconds: float) -> None:
    global _next_request_at
    with _throttle_lock:
        _next_request_at = max(_next_request_at, time.monotonic() + seconds)


def _retry_after_seconds(response: requests.Response) -> float | None:
    raw = response.headers.get("retry-after")
    if not raw:
        return None
    try:
        return max(0.0, float(raw))
    except ValueError:
        pass
    try:
        from email.utils import parsedate_to_datetime

        target = parsedate_to_datetime(raw)
        return max(0.0, target.timestamp() - time.time())
    except (TypeError, ValueError):
        return None


def _rate_limit_backoff_seconds(response: requests.Response, attempt: int) -> float:
    retry_after = _retry_after_seconds(response)
    if retry_after is not None:
        return retry_after
    delay_ms = get_manga_settings()["request_delay_ms"]
    return max(MIN_RATE_LIMIT_BACKOFF_MS / 1000.0, delay_ms * 5 / 1000.0) * (2 ** attempt)


def _nh_headers(extra: dict[str, str] | None = None) -> dict[str, str]:
    settings = get_manga_settings()
    headers = {
        "User-Agent": settings["user_agent"],
        "Referer": f"{API}/",
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
    }
    if extra:
        headers.update(extra)
    if settings["cf_clearance"]:
        headers["Cookie"] = f"cf_clearance={settings['cf_clearance']}"
    return headers


def _nh_fetch(url: str, headers: dict[str, str], timeout: float = 30.0) -> requests.Response:
    attempt = 0
    while True:
        _wait_for_request_turn()
        response = _session.get(url, headers=headers, timeout=timeout)
        if response.status_code != 429 or attempt >= RATE_LIMIT_RETRIES:
            return response
        wait = _rate_limit_backoff_seconds(response, attempt)
        _hold_requests_for(wait)
        time.sleep(wait)
        attempt += 1


def _nh_image_fetch(url: str, headers: dict[str, str], timeout: float = 60.0) -> requests.Response:
    attempt = 0
    while True:
        response = _session.get(url, headers=headers, timeout=timeout)
        if response.status_code != 429 or attempt >= IMAGE_RATE_LIMIT_RETRIES:
            return response
        wait = _retry_after_seconds(response) or (2 ** attempt)
        time.sleep(wait)
        attempt += 1


def _nh_json(path: str) -> Any:
    try:
        response = _nh_fetch(f"{API}{path}", _nh_headers({"Accept": "application/json"}))
    except requests.RequestException as exc:
        raise NhError(f"Network error reaching nHentai: {exc}", 0) from exc
    if response.status_code == 429:
        raise NhError(
            "nHentai rate limited the request. Increase the request delay in Settings and try again.",
            429,
        )
    if response.status_code in (403, 503):
        raise NhError(
            "nHentai blocked the request (Cloudflare). Set a fresh cf_clearance cookie + matching "
            "User-Agent in Settings — the cookie must come from the same browser + network.",
            response.status_code,
        )
    if response.status_code == 404:
        raise NhError("Not found on nHentai.", 404)
    if not response.ok:
        raise NhError(f"nHentai returned {response.status_code}.", response.status_code)
    try:
        return response.json()
    except ValueError as exc:
        raise NhError("nHentai returned invalid JSON.", 502) from exc


def _nh_html(path: str) -> str:
    try:
        response = _nh_fetch(f"{API}{path}", _nh_headers({"Accept": "text/html"}))
    except requests.RequestException as exc:
        raise NhError(f"Network error reaching nHentai: {exc}", 0) from exc
    if response.status_code == 429:
        raise NhError(
            "nHentai rate limited the request. Increase the request delay in Settings and try again.",
            429,
        )
    if response.status_code in (403, 503):
        raise NhError(
            "nHentai blocked the request (Cloudflare). Set a fresh cf_clearance cookie + matching "
            "User-Agent in Settings — the cookie must come from the same browser + network.",
            response.status_code,
        )
    if not response.ok:
        raise NhError(f"nHentai returned {response.status_code}.", response.status_code)
    return response.text


def _tag_count(value: str) -> int:
    normalized = value.strip().lower().replace(",", "")
    match = re.search(r"(\d+(?:\.\d+)?)\s*([kmb])?", normalized)
    if not match:
        return 0
    multiplier = {"k": 1_000, "m": 1_000_000, "b": 1_000_000_000}.get(match.group(2) or "", 1)
    return int(float(match.group(1)) * multiplier)


class _TagDirectoryParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.items: list[dict[str, Any]] = []
        self._current: dict[str, Any] | None = None
        self._depth = 0
        self._field = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {key: value or "" for key, value in attrs}
        if self._current is None and tag == "a":
            path = urlparse(attributes.get("href", "")).path
            match = re.fullmatch(r"/tag/([^/]+)/?", path)
            if match:
                self._current = {
                    "slug": unquote(match.group(1)),
                    "name_parts": [],
                    "count_parts": [],
                    "all_parts": [],
                }
                self._depth = 1
                return
        if self._current is not None:
            self._depth += 1
            classes = set(attributes.get("class", "").split())
            if "name" in classes:
                self._field = "name"
            elif "count" in classes:
                self._field = "count"

    def handle_endtag(self, tag: str) -> None:
        if self._current is None:
            return
        self._depth -= 1
        if self._depth <= 0:
            self._finish_current()
        elif tag == "span":
            self._field = ""

    def handle_data(self, data: str) -> None:
        if self._current is None or not data.strip():
            return
        self._current["all_parts"].append(data.strip())
        if self._field == "name":
            self._current["name_parts"].append(data.strip())
        elif self._field == "count":
            self._current["count_parts"].append(data.strip())

    def _finish_current(self) -> None:
        assert self._current is not None
        slug = str(self._current["slug"])
        name = " ".join(self._current["name_parts"]).strip()
        count_text = " ".join(self._current["count_parts"]).strip()
        all_text = " ".join(self._current["all_parts"]).strip()
        if not count_text:
            match = re.search(r"(\d+(?:\.\d+)?\s*[kmb]?)\s*$", all_text, re.IGNORECASE)
            count_text = match.group(1) if match else ""
        if not name:
            name = all_text[: -len(count_text)].strip() if count_text else all_text
        name = re.sub(r"\s+", " ", name or slug.replace("-", " ")).strip().lower()
        if name and not any(item["slug"] == slug for item in self.items):
            self.items.append({"name": name, "slug": slug, "count": _tag_count(count_text)})
        self._current = None
        self._depth = 0
        self._field = ""


def parse_tag_directory(document: str) -> list[dict[str, Any]]:
    parser = _TagDirectoryParser()
    parser.feed(document)
    parser.close()
    return parser.items[:500]


def tag_directory(sort: str = "popular") -> list[dict[str, Any]]:
    """Return HeH's tag directory; Popular preserves provider order, A–Z sorts that set."""
    global _tag_directory_cache, _tag_directory_cached_at
    sort = sort if sort in {"popular", "a-z"} else "popular"
    with _tag_directory_lock:
        if (
            _tag_directory_cache is None
            or time.monotonic() - _tag_directory_cached_at >= TAG_DIRECTORY_TTL_SECONDS
        ):
            parsed = parse_tag_directory(_nh_html("/tags/"))
            if not parsed:
                raise NhError("HeH returned no readable tags.", 502)
            _tag_directory_cache = parsed
            _tag_directory_cached_at = time.monotonic()
        items = [dict(item) for item in _tag_directory_cache]
    if sort == "a-z":
        items.sort(key=lambda item: (str(item["name"]).casefold(), str(item["slug"])))
    return items


def _get_cdn() -> dict[str, Any]:
    global _cdn_cache, _cdn_cached_at
    with _cdn_lock:
        if _cdn_cache is not None and time.monotonic() - _cdn_cached_at < CDN_TTL_SECONDS:
            return _cdn_cache
        value = _nh_json("/api/v2/cdn")
        if not value.get("image_servers") or not value.get("thumb_servers"):
            raise NhError("nHentai returned no CDN servers.", 502)
        _cdn_cache = value
        _cdn_cached_at = time.monotonic()
        return value


def browse_galleries(
    query: str = "",
    page: int = 1,
    sort: str = "recent",
    language: str = "all",
) -> dict[str, Any]:
    """List/search galleries. Returns {"items": [...], "num_pages": N}."""
    page = max(1, page)
    query = (query or "").strip()
    sort = sort if sort in SORT_TO_V2 else "recent"
    language = (language or "all").strip().lower()
    language_query = f"language:{language}" if language and language != "all" else ""
    search_query = " ".join(part for part in (query, language_query) if part)

    if search_query or sort != "recent":
        params = {"query": search_query or "pages:>0", "page": str(page)}
        v2_sort = SORT_TO_V2[sort]
        if v2_sort != "date":
            params["sort"] = v2_sort
        encoded = "&".join(f"{key}={requests.utils.quote(value)}" for key, value in params.items())
        data = _nh_json(f"/api/v2/search?{encoded}")
    else:
        data = _nh_json(f"/api/v2/galleries?page={page}")
    return {"items": data.get("result", []), "num_pages": data.get("num_pages", 1)}


def get_gallery(gallery_id: int) -> dict[str, Any]:
    """Fetch one gallery's full metadata by id."""
    return _nh_json(f"/api/v2/galleries/{int(gallery_id)}")


def fetch_image_by_path(path: str, kind: str = "image") -> tuple[bytes, str]:
    """Fetch an image by CDN path, trying each mirror. Returns (bytes, content_type)."""
    cdn = _get_cdn()
    servers = cdn["thumb_servers"] if kind == "thumb" else cdn["image_servers"]
    last_status = 0
    for server in servers:
        try:
            response = _nh_image_fetch(f"{server}/{path}", _nh_headers({"Accept": "image/*"}))
        except requests.RequestException:
            continue  # try the next mirror
        if response.ok:
            return response.content, response.headers.get("Content-Type", "image/jpeg")
        if response.status_code == 429:
            raise NhError(
                "nHentai rate limited image downloads. Increase the request delay in Settings and try again.",
                429,
            )
        last_status = response.status_code
        if response.status_code == 404:
            break  # not there under this path; other mirrors won't differ
    raise NhError("Could not fetch image from any nHentai server.", last_status or 502)


def ext_from_path(path: str) -> str:
    match = re.search(r"\.([a-z0-9]+)$", path, re.IGNORECASE)
    return (match.group(1) if match else "jpg").lower()


def best_title(gallery: dict[str, Any]) -> str:
    title = gallery.get("title") or {}
    return title.get("pretty") or title.get("english") or title.get("japanese") or "Untitled"


def best_list_title(item: dict[str, Any]) -> str:
    return item.get("english_title") or item.get("japanese_title") or "Untitled"


def category_of(gallery: dict[str, Any]) -> str:
    for tag in gallery.get("tags") or []:
        if tag.get("type") == "category" and tag.get("name"):
            return str(tag["name"])
    return "manga"
