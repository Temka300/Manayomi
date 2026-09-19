"""Public MangaDex API v5 client and MangaDex@Home image delivery.

MangaDex is deliberately modelled as title -> chapters -> pages.  No account or
authentication state is used.  Metadata requests are rate limited, remote images
are fetched only for an explicit reader/download action, and community at-home
transfers are reported according to MangaDex's current client rules.
"""
from __future__ import annotations

import json
import re
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests

API = "https://api.mangadex.org"
COVER_ORIGIN = "https://uploads.mangadex.org"
REPORT_API = "https://api.mangadex.network/report"
USER_AGENT = "Keivotos-Manayomi/1.1.2 (local single-user desktop client)"

UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)
SAFE_FILE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,254}$")
CONTENT_RATINGS = ("safe", "suggestive", "erotica", "pornographic")
MANGA_STATUSES = ("ongoing", "completed", "hiatus", "cancelled")
PUBLICATION_DEMOGRAPHICS = ("shounen", "shoujo", "josei", "seinen", "none")
TAG_MODES = ("AND", "OR")
TAG_GROUPS = ("content", "format", "genre", "theme")
SORT_OPTIONS: dict[str, tuple[str, str, str]] = {
    "latest": ("latestUploadedChapter", "desc", "Latest chapter"),
    "oldest": ("latestUploadedChapter", "asc", "Oldest chapter update"),
    "relevance": ("relevance", "desc", "Relevance"),
    "rating": ("rating", "desc", "Highest rating"),
    "rating-low": ("rating", "asc", "Lowest rating"),
    "followed": ("followedCount", "desc", "Most followed"),
    "followed-low": ("followedCount", "asc", "Least followed"),
    "year": ("year", "desc", "Newest year"),
    "year-old": ("year", "asc", "Oldest year"),
    "title": ("title", "asc", "Title A–Z"),
    "title-desc": ("title", "desc", "Title Z–A"),
    "created": ("createdAt", "desc", "Recently added"),
    "created-old": ("createdAt", "asc", "Oldest added"),
    "updated": ("updatedAt", "desc", "Recently updated"),
    "updated-old": ("updatedAt", "asc", "Least recently updated"),
}
LANGUAGE_OPTIONS: tuple[tuple[str, str], ...] = (
    ("ar", "Arabic"), ("bn", "Bengali"), ("bg", "Bulgarian"),
    ("my", "Burmese"), ("ca", "Catalan"), ("zh", "Chinese (Simplified)"),
    ("zh-hk", "Chinese (Traditional)"), ("cs", "Czech"), ("da", "Danish"),
    ("nl", "Dutch"), ("en", "English"), ("fil", "Filipino"),
    ("fi", "Finnish"), ("fr", "French"), ("de", "German"),
    ("el", "Greek"), ("he", "Hebrew"), ("hi", "Hindi"),
    ("hu", "Hungarian"), ("id", "Indonesian"), ("it", "Italian"),
    ("ja", "Japanese"), ("kk", "Kazakh"), ("ko", "Korean"),
    ("lt", "Lithuanian"), ("ms", "Malay"), ("mn", "Mongolian"),
    ("ne", "Nepali"), ("no", "Norwegian"), ("fa", "Persian"),
    ("pl", "Polish"), ("pt", "Portuguese"), ("pt-br", "Portuguese (Brazil)"),
    ("ro", "Romanian"), ("ru", "Russian"), ("sr", "Serbo-Croatian"),
    ("es", "Spanish"), ("es-la", "Spanish (Latin America)"),
    ("sv", "Swedish"), ("ta", "Tamil"), ("th", "Thai"),
    ("tr", "Turkish"), ("uk", "Ukrainian"), ("vi", "Vietnamese"),
)
LANGUAGE_NAMES = {
    "en": "english",
    "ja": "japanese",
    "ko": "korean",
    "zh": "chinese",
    "zh-hk": "chinese",
    "pt-br": "portuguese",
    "es-la": "spanish",
}


class MangaDexError(Exception):
    """A MangaDex request failed; ``status`` carries the HTTP-ish code."""

    def __init__(self, message: str, status: int = 0):
        super().__init__(message)
        self.status = status


_session = requests.Session()
_api_lock = threading.Lock()
_next_api_request_at = 0.0
_at_home_lock = threading.Lock()
_at_home_cache: dict[str, tuple[float, dict[str, Any]]] = {}
_tag_lock = threading.Lock()
_tag_cache: tuple[float, list[dict[str, str]]] | None = None


def validate_uuid(value: str, label: str = "MangaDex ID") -> str:
    cleaned = (value or "").strip().lower()
    if not UUID_RE.fullmatch(cleaned):
        raise MangaDexError(f"Invalid {label}.", 400)
    return cleaned


def _wait_for_api_turn() -> None:
    """Stay below MangaDex's approximate five metadata requests/second limit."""
    global _next_api_request_at
    while True:
        with _api_lock:
            now = time.monotonic()
            if now >= _next_api_request_at:
                _next_api_request_at = now + 0.22
                return
            wait = _next_api_request_at - now
        time.sleep(min(wait, 0.25))


def _retry_after(response: requests.Response, attempt: int) -> float:
    raw = response.headers.get("retry-after", "").strip()
    try:
        return max(0.25, float(raw)) if raw else float(2 ** attempt)
    except ValueError:
        return float(2 ** attempt)


def _api_json(
    path: str,
    *,
    params: list[tuple[str, str]] | None = None,
    timeout: float = 30.0,
) -> dict[str, Any]:
    if not path.startswith("/"):
        raise MangaDexError("Invalid MangaDex API path.", 500)
    response: requests.Response | None = None
    for attempt in range(4):
        _wait_for_api_turn()
        try:
            response = _session.get(
                f"{API}{path}",
                params=params,
                headers={"Accept": "application/json", "User-Agent": USER_AGENT},
                timeout=timeout,
            )
        except requests.RequestException as exc:
            if attempt == 3:
                raise MangaDexError(f"Network error reaching MangaDex: {exc}", 0) from exc
            time.sleep(float(2 ** attempt))
            continue
        if response.status_code != 429:
            break
        if attempt == 3:
            raise MangaDexError("MangaDex rate limited the request. Try again shortly.", 429)
        time.sleep(_retry_after(response, attempt))

    assert response is not None
    if response.status_code == 404:
        raise MangaDexError("Not found on MangaDex.", 404)
    if not response.ok:
        message = f"MangaDex returned {response.status_code}."
        try:
            body = response.json()
            errors = body.get("errors") if isinstance(body, dict) else None
            if isinstance(errors, list) and errors:
                message = str(errors[0].get("detail") or errors[0].get("title") or message)
        except ValueError:
            pass
        raise MangaDexError(message, response.status_code)
    if len(response.content) > 8 * 1024 * 1024:
        raise MangaDexError("MangaDex metadata response was unexpectedly large.", 502)
    try:
        body = response.json()
    except ValueError as exc:
        raise MangaDexError("MangaDex returned invalid JSON.", 502) from exc
    if not isinstance(body, dict):
        raise MangaDexError("MangaDex returned an invalid response.", 502)
    return body


def _localized(value: Any, preferred: tuple[str, ...] = ("en", "ja-ro", "ja")) -> str:
    if not isinstance(value, dict):
        return ""
    for language in preferred:
        text = value.get(language)
        if isinstance(text, str) and text.strip():
            return text.strip()
    for text in value.values():
        if isinstance(text, str) and text.strip():
            return text.strip()
    return ""


def _relationships(data: dict[str, Any], relation_type: str) -> list[dict[str, Any]]:
    return [
        relation
        for relation in data.get("relationships") or []
        if isinstance(relation, dict) and relation.get("type") == relation_type
    ]


def _person_names(data: dict[str, Any], relation_type: str) -> list[str]:
    names: list[str] = []
    for relation in _relationships(data, relation_type):
        attributes = relation.get("attributes") or {}
        name = attributes.get("name")
        if isinstance(name, str) and name.strip() and name.strip() not in names:
            names.append(name.strip())
    return names


def normalize_title(data: dict[str, Any]) -> dict[str, Any]:
    attributes = data.get("attributes") or {}
    title_map = attributes.get("title") or {}
    alternate_titles = attributes.get("altTitles") or []
    title = _localized(title_map) or "Untitled"
    cover_filename = ""
    for relation in _relationships(data, "cover_art"):
        filename = (relation.get("attributes") or {}).get("fileName")
        if isinstance(filename, str) and SAFE_FILE_RE.fullmatch(filename):
            cover_filename = filename
            break
    tags: list[dict[str, str]] = []
    for tag in attributes.get("tags") or []:
        tag_attributes = tag.get("attributes") or {}
        name = _localized(tag_attributes.get("name"))
        if name:
            tags.append({"id": str(tag.get("id") or ""), "name": name, "group": str(tag_attributes.get("group") or "tag")})
    alt_values = [_localized(value) for value in alternate_titles if isinstance(value, dict)]
    return {
        "id": validate_uuid(str(data.get("id") or ""), "MangaDex title ID"),
        "title": title,
        "titles": title_map if isinstance(title_map, dict) else {},
        "alternate_titles": [value for value in alt_values if value],
        "description": _localized(attributes.get("description")),
        "authors": _person_names(data, "author"),
        "artists": _person_names(data, "artist"),
        "cover_filename": cover_filename,
        "tags": tags,
        "status": str(attributes.get("status") or ""),
        "year": attributes.get("year") if isinstance(attributes.get("year"), int) else None,
        "original_language": str(attributes.get("originalLanguage") or ""),
        "available_languages": [str(value) for value in attributes.get("availableTranslatedLanguages") or [] if isinstance(value, str)],
        "content_rating": str(attributes.get("contentRating") or ""),
        "publication_demographic": str(attributes.get("publicationDemographic") or ""),
        "last_volume": attributes.get("lastVolume"),
        "last_chapter": attributes.get("lastChapter"),
        "links": attributes.get("links") if isinstance(attributes.get("links"), dict) else {},
        "official_links": attributes.get("officialLinks") if isinstance(attributes.get("officialLinks"), list) else [],
        "created_at": attributes.get("createdAt"),
        "updated_at": attributes.get("updatedAt"),
    }


def normalize_chapter(data: dict[str, Any]) -> dict[str, Any]:
    attributes = data.get("attributes") or {}
    manga_relations = _relationships(data, "manga")
    groups = _person_names(data, "scanlation_group")
    return {
        "id": validate_uuid(str(data.get("id") or ""), "MangaDex chapter ID"),
        "manga_id": validate_uuid(str(manga_relations[0].get("id") or ""), "MangaDex title ID") if manga_relations else "",
        "title": str(attributes.get("title") or "").strip(),
        "volume": attributes.get("volume"),
        "chapter": attributes.get("chapter"),
        "pages": int(attributes.get("pages") or 0),
        "translated_language": str(attributes.get("translatedLanguage") or ""),
        "external_url": str(attributes.get("externalUrl") or ""),
        "publish_at": attributes.get("publishAt"),
        "readable_at": attributes.get("readableAt"),
        "created_at": attributes.get("createdAt"),
        "updated_at": attributes.get("updatedAt"),
        "unavailable": bool(attributes.get("unavailable")),
        "scanlation_groups": groups,
    }


def search_titles(
    query: str = "",
    *,
    page: int = 1,
    per_page: int = 20,
    sort: str = "latest",
    language: str = "all",
    original_languages: list[str] | None = None,
    content_ratings: list[str] | None = None,
    publication_demographics: list[str] | None = None,
    statuses: list[str] | None = None,
    included_tag_ids: list[str] | None = None,
    tags_mode: str = "AND",
    excluded_tag_names: list[str] | None = None,
) -> dict[str, Any]:
    per_page = max(1, min(100, int(per_page)))
    page = max(1, int(page))
    params: list[tuple[str, str]] = [
        ("limit", str(per_page)),
        ("offset", str((page - 1) * per_page)),
        ("includes[]", "author"),
        ("includes[]", "artist"),
        ("includes[]", "cover_art"),
        ("hasAvailableChapters", "true"),
    ]
    cleaned_query = (query or "").strip()
    if cleaned_query:
        params.append(("title", cleaned_query[:200]))
    known_languages = {code for code, _label in LANGUAGE_OPTIONS}
    if language and language != "all":
        if language not in known_languages:
            raise MangaDexError("Invalid translated language.", 400)
        params.append(("availableTranslatedLanguage[]", language))
    for original_language in _allowed_values(
        original_languages or [], known_languages, "original language"
    ):
        params.append(("originalLanguage[]", original_language))
    selected_ratings = _allowed_values(
        content_ratings or list(CONTENT_RATINGS), set(CONTENT_RATINGS), "content rating"
    )
    for rating in selected_ratings:
        params.append(("contentRating[]", rating))
    for demographic in _allowed_values(
        publication_demographics or [],
        set(PUBLICATION_DEMOGRAPHICS),
        "publication demographic",
    ):
        params.append(("publicationDemographic[]", demographic))
    for status in _allowed_values(statuses or [], set(MANGA_STATUSES), "status"):
        params.append(("status[]", status))
    tag_mode = (tags_mode or "AND").strip().upper()
    if tag_mode not in TAG_MODES:
        raise MangaDexError("Invalid tags mode.", 400)
    selected_tag_ids = _validated_tag_ids(included_tag_ids or [])
    for tag_id in selected_tag_ids:
        params.append(("includedTags[]", tag_id))
    if selected_tag_ids:
        params.append(("includedTagsMode", tag_mode))
    excluded_ids = tag_ids_for_names(excluded_tag_names or [])
    for tag_id in excluded_ids:
        params.append(("excludedTags[]", tag_id))
    if excluded_ids:
        params.append(("excludedTagsMode", "OR"))
    if sort not in SORT_OPTIONS:
        raise MangaDexError("Invalid MangaDex sort.", 400)
    order, direction, _label = SORT_OPTIONS[sort]
    if order == "relevance" and not cleaned_query:
        order = "latestUploadedChapter"
    params.append((f"order[{order}]", direction))
    body = _api_json("/manga", params=params)
    items = [normalize_title(item) for item in body.get("data") or [] if isinstance(item, dict)]
    total = max(0, int(body.get("total") or 0))
    return {
        "items": items,
        "total": total,
        "page": page,
        "per_page": per_page,
        "num_pages": max(1, (total + per_page - 1) // per_page),
    }


def _allowed_values(values: list[str], allowed: set[str], label: str) -> list[str]:
    cleaned = list(
        dict.fromkeys(str(value).strip().lower() for value in values if str(value).strip())
    )
    unknown = [value for value in cleaned if value not in allowed]
    if unknown:
        raise MangaDexError(f"Invalid {label}: {unknown[0]}.", 400)
    return cleaned


def _validated_tag_ids(values: list[str]) -> list[str]:
    return list(
        dict.fromkeys(validate_uuid(value, "MangaDex tag ID") for value in values)
    )


def tag_catalog() -> list[dict[str, str]]:
    """Return MangaDex's current public tag catalog, cached for thirty minutes."""
    global _tag_cache
    with _tag_lock:
        if _tag_cache is None or _tag_cache[0] <= time.monotonic():
            body = _api_json("/manga/tag")
            catalog: list[dict[str, str]] = []
            for item in body.get("data") or []:
                if not isinstance(item, dict):
                    continue
                attributes = item.get("attributes") or {}
                name = _localized(attributes.get("name"))
                identifier = str(item.get("id") or "")
                group = str(attributes.get("group") or "")
                if name and group in TAG_GROUPS and UUID_RE.fullmatch(identifier):
                    catalog.append(
                        {"id": identifier.lower(), "name": name, "group": group}
                    )
            catalog.sort(
                key=lambda tag: (TAG_GROUPS.index(tag["group"]), tag["name"].casefold())
            )
            _tag_cache = (time.monotonic() + 30 * 60, catalog)
        catalog = _tag_cache[1]
    return [dict(tag) for tag in catalog]


def tag_ids_for_names(names: list[str]) -> list[str]:
    """Resolve ignored tag names to official MangaDex tag UUIDs."""
    wanted = {str(name).strip().casefold() for name in names if str(name).strip()}
    if not wanted:
        return []
    mapping = {tag["name"].casefold(): tag["id"] for tag in tag_catalog()}
    return sorted({mapping[name] for name in wanted if name in mapping})


def filter_catalog() -> dict[str, Any]:
    """Describe MangaDex browse filters without copying its changing tag list."""
    tags = tag_catalog()
    return {
        "languages": [
            {"value": code, "label": label} for code, label in LANGUAGE_OPTIONS
        ],
        "content_ratings": [
            {"value": value, "label": value.replace("_", " ").title()}
            for value in CONTENT_RATINGS
        ],
        "publication_demographics": [
            {"value": value, "label": "None" if value == "none" else value.title()}
            for value in PUBLICATION_DEMOGRAPHICS
        ],
        "statuses": [
            {"value": value, "label": value.title()} for value in MANGA_STATUSES
        ],
        "sorts": [
            {"value": value, "label": details[2]}
            for value, details in SORT_OPTIONS.items()
        ],
        "tag_modes": [
            {"value": "AND", "label": "Match all"},
            {"value": "OR", "label": "Match any"},
        ],
        "tag_groups": {
            group: [tag for tag in tags if tag["group"] == group]
            for group in TAG_GROUPS
        },
    }


def get_title(title_id: str) -> dict[str, Any]:
    title_id = validate_uuid(title_id, "MangaDex title ID")
    params = [("includes[]", value) for value in ("author", "artist", "cover_art")]
    body = _api_json(f"/manga/{title_id}", params=params)
    data = body.get("data")
    if not isinstance(data, dict):
        raise MangaDexError("MangaDex returned no title information.", 502)
    return normalize_title(data)


def list_chapters(
    title_id: str,
    *,
    language: str = "all",
    limit: int = 500,
    offset: int = 0,
) -> dict[str, Any]:
    title_id = validate_uuid(title_id, "MangaDex title ID")
    limit = max(1, min(500, int(limit)))
    offset = max(0, int(offset))
    params: list[tuple[str, str]] = [
        ("limit", str(limit)),
        ("offset", str(offset)),
        ("includes[]", "scanlation_group"),
        ("order[volume]", "asc"),
        ("order[chapter]", "asc"),
        ("order[publishAt]", "asc"),
        ("includeEmptyPages", "0"),
        ("includeFuturePublishAt", "0"),
        ("includeUnavailable", "0"),
    ]
    if language and language != "all":
        params.append(("translatedLanguage[]", language))
    for rating in CONTENT_RATINGS:
        params.append(("contentRating[]", rating))
    body = _api_json(f"/manga/{title_id}/feed", params=params)
    items = [normalize_chapter(item) for item in body.get("data") or [] if isinstance(item, dict)]
    return {"items": items, "total": max(0, int(body.get("total") or 0)), "limit": limit, "offset": offset}


def get_chapter(chapter_id: str) -> dict[str, Any]:
    chapter_id = validate_uuid(chapter_id, "MangaDex chapter ID")
    params = [("includes[]", "manga"), ("includes[]", "scanlation_group")]
    body = _api_json(f"/chapter/{chapter_id}", params=params)
    data = body.get("data")
    if not isinstance(data, dict):
        raise MangaDexError("MangaDex returned no chapter information.", 502)
    return normalize_chapter(data)


def _at_home(chapter_id: str, *, refresh: bool = False) -> dict[str, Any]:
    chapter_id = validate_uuid(chapter_id, "MangaDex chapter ID")
    with _at_home_lock:
        cached = _at_home_cache.get(chapter_id)
        if not refresh and cached and cached[0] > time.monotonic():
            return cached[1]
    body = _api_json(f"/at-home/server/{chapter_id}")
    chapter = body.get("chapter") or {}
    base_url = str(body.get("baseUrl") or "").rstrip("/")
    digest = str(chapter.get("hash") or "")
    data = [str(value) for value in chapter.get("data") or []]
    saver = [str(value) for value in chapter.get("dataSaver") or []]
    if not base_url.startswith("https://") or not digest or not data:
        raise MangaDexError("MangaDex returned incomplete chapter page information.", 502)
    if any(not SAFE_FILE_RE.fullmatch(name) for name in [*data, *saver]):
        raise MangaDexError("MangaDex returned an invalid page filename.", 502)
    value = {"base_url": base_url, "hash": digest, "data": data, "data_saver": saver}
    with _at_home_lock:
        _at_home_cache[chapter_id] = (time.monotonic() + 14 * 60, value)
        if len(_at_home_cache) > 200:
            oldest = min(_at_home_cache, key=lambda key: _at_home_cache[key][0])
            _at_home_cache.pop(oldest, None)
    return value


def chapter_pages(chapter_id: str) -> dict[str, Any]:
    chapter_id = validate_uuid(chapter_id, "MangaDex chapter ID")
    home = _at_home(chapter_id)
    return {"chapter_id": chapter_id, "pages": len(home["data"]), "data_saver": len(home["data_saver"])}


def _requires_report(base_url: str) -> bool:
    hostname = (urlparse(base_url).hostname or "").lower()
    return bool(hostname and hostname != "mangadex.org" and not hostname.endswith(".mangadex.org"))


def _report_image(url: str, response: requests.Response | None, success: bool, duration_ms: int) -> None:
    if not _requires_report(url):
        return
    payload = {
        "url": url,
        "success": bool(success),
        "cached": bool(response is not None and "HIT" in response.headers.get("X-Cache", "").upper()),
        "bytes": len(response.content) if response is not None else 0,
        "duration": max(0, int(duration_ms)),
    }
    try:
        _session.post(
            REPORT_API,
            json=payload,
            headers={"User-Agent": USER_AGENT, "Content-Type": "application/json"},
            timeout=10,
        )
    except requests.RequestException:
        pass  # reporting failure must not discard a successfully fetched page


def fetch_chapter_page(chapter_id: str, number: int, quality: str = "data-saver") -> tuple[bytes, str, str]:
    chapter_id = validate_uuid(chapter_id, "MangaDex chapter ID")
    if quality not in {"data", "data-saver"}:
        raise MangaDexError("Invalid MangaDex page quality.", 400)
    number = int(number)
    for attempt in range(2):
        home = _at_home(chapter_id, refresh=attempt > 0)
        use_saver = quality == "data-saver" and bool(home["data_saver"])
        filenames = home["data_saver"] if use_saver else home["data"]
        path_quality = "data-saver" if use_saver else "data"
        if number < 0 or number >= len(filenames):
            raise MangaDexError("MangaDex chapter page not found.", 404)
        url = f"{home['base_url']}/{path_quality}/{home['hash']}/{filenames[number]}"
        started = time.monotonic()
        response: requests.Response | None = None
        try:
            response = _session.get(url, headers={"User-Agent": USER_AGENT}, timeout=60)
            duration = round((time.monotonic() - started) * 1000)
            success = response.ok and len(response.content) <= 80 * 1024 * 1024
            _report_image(url, response, success, duration)
            if success:
                return response.content, response.headers.get("content-type", "image/jpeg"), filenames[number]
        except requests.RequestException:
            duration = round((time.monotonic() - started) * 1000)
            _report_image(url, response, False, duration)
        with _at_home_lock:
            _at_home_cache.pop(chapter_id, None)
    raise MangaDexError("MangaDex could not deliver this chapter page.", 502)


def fetch_cover(title_id: str, filename: str, size: int = 512) -> tuple[bytes, str]:
    title_id = validate_uuid(title_id, "MangaDex title ID")
    if not SAFE_FILE_RE.fullmatch(filename or ""):
        raise MangaDexError("Invalid MangaDex cover filename.", 400)
    suffix = f".{size}.jpg" if size in {256, 512} else ""
    try:
        response = _session.get(
            f"{COVER_ORIGIN}/covers/{title_id}/{filename}{suffix}",
            headers={"User-Agent": USER_AGENT},
            timeout=45,
        )
    except requests.RequestException as exc:
        raise MangaDexError(f"Network error fetching MangaDex cover: {exc}", 0) from exc
    if not response.ok:
        raise MangaDexError(f"MangaDex cover returned {response.status_code}.", response.status_code)
    if len(response.content) > 30 * 1024 * 1024:
        raise MangaDexError("MangaDex cover was unexpectedly large.", 502)
    return response.content, response.headers.get("content-type", "image/jpeg")


def _chapter_label(chapter: dict[str, Any]) -> str:
    pieces = []
    if chapter.get("volume") not in (None, ""):
        pieces.append(f"Vol. {chapter['volume']}")
    if chapter.get("chapter") not in (None, ""):
        pieces.append(f"Ch. {chapter['chapter']}")
    if chapter.get("title"):
        pieces.append(str(chapter["title"]))
    return " — ".join(pieces) or "Unnumbered chapter"


def _unix_seconds(value: Any) -> int | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp())
    except ValueError:
        return None


def library_gallery(
    title: dict[str, Any],
    chapter: dict[str, Any],
    local_gallery_id: int,
) -> dict[str, Any]:
    """Convert MangaDex title/chapter metadata to Manayomi's indexed card shape."""
    title_text = str(title.get("title") or "Untitled")
    display = f"{title_text} — {_chapter_label(chapter)}"
    tags = [
        {"id": None, "name": str(tag.get("name") or "").strip().lower(), "type": str(tag.get("group") or "tag")}
        for tag in title.get("tags") or []
        if str(tag.get("name") or "").strip()
    ]
    language = str(chapter.get("translated_language") or "").lower()
    if language:
        tags.append({"id": None, "name": LANGUAGE_NAMES.get(language, language), "type": "language"})
    for artist in title.get("artists") or []:
        tags.append({"id": None, "name": str(artist).strip().lower(), "type": "artist"})
    cover_filename = str(title.get("cover_filename") or "")
    return {
        "source": "mangadex",
        "id": int(local_gallery_id),
        "external_id": str(chapter["id"]),
        "parent_external_id": str(title["id"]),
        "media_id": str(chapter["id"]),
        "title": {
            "english": display,
            "japanese": "",
            "pretty": display,
        },
        "num_pages": int(chapter.get("pages") or 0),
        "num_favorites": None,
        "scanlator": ", ".join(chapter.get("scanlation_groups") or []),
        "upload_date": _unix_seconds(chapter.get("publish_at")),
        "tags": tags,
        "cover": {"path": cover_filename},
        "mangadex": {"title": title, "chapter": chapter},
    }


def sidecar_path(cbz_path: str | Path) -> Path:
    return Path(cbz_path).parent / "mangadex.json"


def write_download_sidecar(
    cbz_path: str | Path,
    title: dict[str, Any],
    chapter: dict[str, Any],
) -> None:
    target = sidecar_path(cbz_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(
            {"schema_version": 1, "source": "mangadex", "title": title, "chapter": chapter},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    temporary.replace(target)


def read_download_sidecar(cbz_path: str | Path) -> dict[str, Any] | None:
    target = sidecar_path(cbz_path)
    if not target.is_file():
        return None
    try:
        body = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(body, dict) or body.get("source") != "mangadex":
        return None
    title = body.get("title")
    chapter = body.get("chapter")
    if not isinstance(title, dict) or not isinstance(chapter, dict):
        return None
    try:
        validate_uuid(str(title.get("id") or ""), "MangaDex title ID")
        validate_uuid(str(chapter.get("id") or ""), "MangaDex chapter ID")
    except MangaDexError:
        return None
    return body
