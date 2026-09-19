"""Parse user-supplied URLs into source-neutral Reddit capture targets.

Slice 0 is intentionally offline.  This module identifies what a URL means but
does not open it, resolve redirects, or contact Reddit or an archive service.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Any
from urllib.parse import parse_qs, quote, unquote, urlencode, urlsplit, urlunsplit


REDDIT_PAGE_HOSTS = {
    "reddit.com",
    "www.reddit.com",
    "old.reddit.com",
    "new.reddit.com",
    "np.reddit.com",
    "m.reddit.com",
}
REDDIT_SHORT_HOSTS = {"redd.it", "www.redd.it"}
REDDIT_ASSET_HOSTS = {
    "i.redd.it",
    "v.redd.it",
    "preview.redd.it",
    "external-preview.redd.it",
}
BLOCKED_WEB_ARCHIVE_HOSTS = {"web.archive.org", "www.web.archive.org"}
BLOCKED_WEB_ARCHIVE_SUFFIXES = (".warc", ".warc.gz", ".wacz")
KNOWN_ASSET_SUFFIXES = {
    ".avif",
    ".gif",
    ".jpeg",
    ".jpg",
    ".m3u8",
    ".mp4",
    ".png",
    ".svg",
    ".webm",
    ".webp",
}
SUBREDDIT_RE = re.compile(r"^[A-Za-z0-9_]{2,32}$")
USERNAME_RE = re.compile(r"^[A-Za-z0-9_-]{1,32}$")
THING_ID_RE = re.compile(r"^[A-Za-z0-9]+$")


class TargetParseError(ValueError):
    """Raised when a capture target is unsafe or cannot be interpreted."""


@dataclass(frozen=True)
class CaptureTarget:
    """One canonical capture scope derived without network access."""

    kind: str
    input_value: str
    canonical_url: str
    subreddit: str | None = None
    post_id: str | None = None
    comment_id: str | None = None
    username: str | None = None
    query: str | None = None
    sort: str | None = None
    time_filter: str | None = None
    def as_dict(self) -> dict[str, Any]:
        """Return a stable JSON-serializable representation."""
        return asdict(self)


def _validate_subreddit(value: str) -> str:
    value = value.strip()
    if not SUBREDDIT_RE.fullmatch(value):
        raise TargetParseError(f"Invalid subreddit name: {value!r}")
    return value


def _validate_username(value: str) -> str:
    value = value.strip()
    if not USERNAME_RE.fullmatch(value):
        raise TargetParseError(f"Invalid Reddit username: {value!r}")
    return value


def _validate_thing_id(value: str, label: str) -> str:
    value = value.strip().lower()
    if not THING_ID_RE.fullmatch(value):
        raise TargetParseError(f"Invalid Reddit {label}: {value!r}")
    return value


def _safe_split(value: str):
    parsed = urlsplit(value)
    if parsed.scheme.lower() not in {"http", "https"}:
        raise TargetParseError("Only http:// and https:// URLs are supported")
    if not parsed.hostname:
        raise TargetParseError("The URL has no hostname")
    if parsed.username or parsed.password:
        raise TargetParseError("URLs containing credentials are not accepted")
    return parsed


def _external_url(parsed) -> str:
    host = (parsed.hostname or "").lower()
    port = parsed.port
    netloc = host if port is None else f"{host}:{port}"
    return urlunsplit(
        (
            "https",
            netloc,
            parsed.path or "/",
            parsed.query,
            "",
        )
    )


def _query_value(query: dict[str, list[str]], key: str) -> str | None:
    values = query.get(key)
    return values[0] if values else None


def _search_target(
    input_value: str,
    subreddit: str | None,
    query_values: dict[str, list[str]],
) -> CaptureTarget:
    query = _query_value(query_values, "q") or ""
    sort = _query_value(query_values, "sort")
    time_filter = _query_value(query_values, "t")
    canonical_query = {"q": query}
    if sort:
        canonical_query["sort"] = sort
    if time_filter:
        canonical_query["t"] = time_filter
    if subreddit:
        canonical_query["restrict_sr"] = "on"
        path = f"/r/{quote(subreddit)}/search/"
    else:
        path = "/search/"
    return CaptureTarget(
        kind="search",
        input_value=input_value,
        canonical_url=f"https://www.reddit.com{path}?{urlencode(canonical_query)}",
        subreddit=subreddit,
        query=query,
        sort=sort,
        time_filter=time_filter,
    )


def _reddit_target(value: str, parsed) -> CaptureTarget:
    host = (parsed.hostname or "").lower()
    parts = [unquote(part) for part in parsed.path.split("/") if part]
    query_values = parse_qs(parsed.query, keep_blank_values=True)

    if host in REDDIT_SHORT_HOSTS:
        if len(parts) != 1:
            raise TargetParseError("A redd.it URL must contain exactly one post ID")
        post_id = _validate_thing_id(parts[0], "post ID")
        return CaptureTarget(
            kind="post",
            input_value=value,
            canonical_url=f"https://www.reddit.com/comments/{post_id}/",
            post_id=post_id,
        )

    if host in REDDIT_ASSET_HOSTS:
        return CaptureTarget(
            kind="asset",
            input_value=value,
            canonical_url=_external_url(parsed),
        )

    if not parts:
        if "q" in query_values:
            return _search_target(value, None, query_values)
        raise TargetParseError("A Reddit home-page URL is not a bounded capture target")

    first = parts[0].lower()
    if first == "comments" and len(parts) >= 2:
        post_id = _validate_thing_id(parts[1], "post ID")
        comment_id = None
        if len(parts) >= 4 and parts[3] not in {"_", ""}:
            comment_id = _validate_thing_id(parts[3], "comment ID")
        canonical = f"https://www.reddit.com/comments/{post_id}/"
        if comment_id:
            canonical += f"_/{comment_id}/"
        return CaptureTarget(
            kind="post",
            input_value=value,
            canonical_url=canonical,
            post_id=post_id,
            comment_id=comment_id,
        )

    if first in {"user", "u"} and len(parts) >= 2:
        username = _validate_username(parts[1])
        listing = parts[2].lower() if len(parts) >= 3 else None
        canonical = f"https://www.reddit.com/user/{quote(username)}/"
        if listing:
            canonical += f"{quote(listing)}/"
        return CaptureTarget(
            kind="user",
            input_value=value,
            canonical_url=canonical,
            username=username,
            sort=listing,
        )

    if first == "search":
        return _search_target(value, None, query_values)

    if first != "r" or len(parts) < 2:
        raise TargetParseError("Unsupported Reddit URL")

    subreddit = _validate_subreddit(parts[1])
    if len(parts) == 2:
        return CaptureTarget(
            kind="subreddit",
            input_value=value,
            canonical_url=f"https://www.reddit.com/r/{quote(subreddit)}/",
            subreddit=subreddit,
        )

    action = parts[2].lower()
    if action == "comments" and len(parts) >= 4:
        post_id = _validate_thing_id(parts[3], "post ID")
        comment_id = None
        if len(parts) >= 6 and parts[5] not in {"_", ""}:
            comment_id = _validate_thing_id(parts[5], "comment ID")
        canonical = (
            f"https://www.reddit.com/r/{quote(subreddit)}/comments/{post_id}/"
        )
        if comment_id:
            canonical += f"_/{comment_id}/"
        return CaptureTarget(
            kind="post",
            input_value=value,
            canonical_url=canonical,
            subreddit=subreddit,
            post_id=post_id,
            comment_id=comment_id,
        )

    if action == "search":
        return _search_target(value, subreddit, query_values)

    if action in {"new", "hot", "top", "controversial", "rising"}:
        time_filter = _query_value(query_values, "t")
        query = f"t={quote(time_filter)}" if time_filter else ""
        canonical = (
            f"https://www.reddit.com/r/{quote(subreddit)}/{quote(action)}/"
        )
        if query:
            canonical += f"?{query}"
        return CaptureTarget(
            kind="subreddit",
            input_value=value,
            canonical_url=canonical,
            subreddit=subreddit,
            sort=action,
            time_filter=time_filter,
        )

    raise TargetParseError("Unsupported Reddit subreddit URL")


def parse_capture_target(value: str) -> CaptureTarget:
    """Parse a subreddit name or URL without performing network access."""
    value = value.strip()
    if not value:
        raise TargetParseError("Capture target cannot be empty")

    name_match = re.fullmatch(r"(?:/?r/)?([A-Za-z0-9_]{2,32})/?", value)
    if name_match and "://" not in value:
        subreddit = _validate_subreddit(name_match.group(1))
        return CaptureTarget(
            kind="subreddit",
            input_value=value,
            canonical_url=f"https://www.reddit.com/r/{quote(subreddit)}/",
            subreddit=subreddit,
        )

    parsed = _safe_split(value)
    host = (parsed.hostname or "").lower()
    lowered_path = parsed.path.lower()
    if host in BLOCKED_WEB_ARCHIVE_HOSTS or lowered_path.endswith(
        BLOCKED_WEB_ARCHIVE_SUFFIXES
    ):
        raise TargetParseError(
            "Web-archive URLs and WARC/WACZ inputs are outside this module"
        )
    if (
        host in REDDIT_PAGE_HOSTS
        or host in REDDIT_SHORT_HOSTS
        or host in REDDIT_ASSET_HOSTS
    ):
        return _reddit_target(value, parsed)

    suffix = ""
    for candidate in KNOWN_ASSET_SUFFIXES:
        if lowered_path.endswith(candidate):
            suffix = candidate
            break
    return CaptureTarget(
        kind="asset" if suffix else "external",
        input_value=value,
        canonical_url=_external_url(parsed),
    )
