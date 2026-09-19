"""Offline extraction and classification of outbound links in Reddit records."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import html
from pathlib import PurePosixPath
import re
from typing import Iterable
from urllib.parse import unquote, urlsplit


URL_RE = re.compile(r"https?://[^\s<>()\[\]{}\"']+", re.IGNORECASE)
TRAILING_PUNCTUATION = ".,;:!?)]}"
MEDIAFIRE_HOST = "mediafire.com"
REDDIT_PAGE_HOSTS = {"reddit.com", "redd.it"}


@dataclass(frozen=True)
class OutboundLink:
    url: str
    host: str
    label: str
    download_kind: str | None

    def as_dict(self) -> dict[str, str | None]:
        return asdict(self)


def is_mediafire_host(host: str) -> bool:
    normalized = host.casefold().rstrip(".")
    return normalized == MEDIAFIRE_HOST or normalized.endswith(
        "." + MEDIAFIRE_HOST
    )


def is_reddit_page_host(host: str) -> bool:
    normalized = host.casefold().rstrip(".")
    return any(
        normalized == root or normalized.endswith("." + root)
        for root in REDDIT_PAGE_HOSTS
    )


def _link_label(url: str, host: str) -> str:
    try:
        path = unquote(urlsplit(url).path)
        pieces = [piece for piece in path.split("/") if piece]
        if (
            is_mediafire_host(host)
            and len(pieces) >= 3
            and pieces[0].casefold() == "file"
        ):
            name = pieces[2].strip()
        else:
            name = PurePosixPath(path).name.strip()
    except ValueError:
        name = ""
    if name and name.casefold() not in {"file", "download"}:
        return name.replace("_", " ")
    return host


def normalize_outbound_url(value: str) -> str | None:
    candidate = html.unescape(value).strip().rstrip(TRAILING_PUNCTUATION)
    if not candidate or len(candidate) > 2048:
        return None
    try:
        parsed = urlsplit(candidate)
        host = (parsed.hostname or "").casefold().rstrip(".")
        port = parsed.port
    except ValueError:
        return None
    if (
        parsed.scheme.casefold() not in {"http", "https"}
        or not host
        or parsed.username is not None
        or parsed.password is not None
        or (
            parsed.scheme.casefold() == "http"
            and port not in {None, 80}
        )
        or (
            parsed.scheme.casefold() == "https"
            and port not in {None, 443}
        )
    ):
        return None
    return candidate


def extract_outbound_links(
    primary_url: str | None,
    body: str | None,
) -> tuple[OutboundLink, ...]:
    """Return stable, de-duplicated links without contacting any remote host."""
    values: list[str] = []
    if primary_url:
        values.append(primary_url)
    values.extend(match.group(0) for match in URL_RE.finditer(body or ""))

    links: list[OutboundLink] = []
    seen: set[str] = set()
    for value in values:
        normalized = normalize_outbound_url(value)
        if normalized is None or normalized in seen:
            continue
        seen.add(normalized)
        parsed = urlsplit(normalized)
        host = (parsed.hostname or "").casefold().rstrip(".")
        download_kind = None
        if parsed.scheme.casefold() == "https":
            if is_mediafire_host(host) and parsed.path.casefold().startswith("/file/"):
                download_kind = "mediafire"
            else:
                download_kind = "https-file"
        links.append(
            OutboundLink(
                url=normalized,
                host=host,
                label=_link_label(normalized, host),
                download_kind=download_kind,
            )
        )
    return tuple(links)


def link_urls(
    primary_url: str | None,
    body: str | None,
    *,
    excluding: Iterable[str] = (),
) -> tuple[str, ...]:
    excluded = set(excluding)
    return tuple(
        link.url
        for link in extract_outbound_links(primary_url, body)
        if (
            link.download_kind is not None
            and not is_reddit_page_host(link.host)
            and link.url not in excluded
        )
    )
