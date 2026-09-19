"""Library search-string parser (Python port of tags.ts parseLibraryQuery).

Supports nHentai-style syntax: bare words are any-category tags, ``-`` negates,
quotes keep multi-word tags together, and prefixes scope or filter:
``artist:foo character:"bar baz" -tag:x pages:>20 favorites:>=100
uploaded:<30d title:"..." jtitle:"..."``.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

TOKEN_RE = re.compile(r'-?[a-zA-Z]+:"[^"]*"|-?"[^"]*"|-?\S+')
NUM_RE = re.compile(r"^(>=|<=|>|<)?\s*(\d+)$")
DATE_RE = re.compile(r"^(>=|<=|>|<)?\s*(\d+)\s*([dwmy])?$", re.IGNORECASE)

# tag:/tags: match any category (backwards-compatible); the rest scope to their category.
CATEGORY_OF: dict[str, str | None] = {
    "tag": None,
    "tags": None,
    "artist": "artist",
    "parody": "parody",
    "character": "character",
    "group": "group",
    "language": "language",
    "category": "category",
}

DATE_UNIT_DAYS = {"d": 1, "w": 7, "m": 30, "y": 365}


def normalize_tag(raw: str) -> str:
    return re.sub(r"\s+", " ", (raw or "").strip().lower())


@dataclass
class NumFilter:
    op: str
    value: int


@dataclass
class DateFilter:
    op: str
    days: int


@dataclass
class ScopedTag:
    name: str
    category: str
    negate: bool


@dataclass
class LibraryQuery:
    include: list[str] = field(default_factory=list)
    exclude: list[str] = field(default_factory=list)
    scoped: list[ScopedTag] = field(default_factory=list)
    title: str = ""
    jtitle: str = ""
    pages: NumFilter | None = None
    favorites: NumFilter | None = None
    uploaded: DateFilter | None = None


def _parse_num(rest: str) -> NumFilter | None:
    match = NUM_RE.match(rest.strip())
    return NumFilter(match.group(1) or "=", int(match.group(2))) if match else None


def _parse_date(rest: str) -> DateFilter | None:
    match = DATE_RE.match(rest.strip())
    if not match:
        return None
    unit = (match.group(3) or "d").lower()
    return DateFilter(match.group(1) or "=", int(match.group(2)) * DATE_UNIT_DAYS[unit])


def parse_library_query(query: str) -> LibraryQuery:
    result = LibraryQuery()
    title_parts: list[str] = []
    jtitle_parts: list[str] = []

    for raw in TOKEN_RE.findall(query or ""):
        token = raw
        negate = token.startswith("-")
        if negate:
            token = token[1:]
        colon = token.find(":")
        prefix = token[:colon].lower() if colon > 0 else ""
        body = token[colon + 1:] if colon > 0 else token
        unquoted = body.strip('"').strip()

        if prefix in CATEGORY_OF:
            name = normalize_tag(unquoted)
            if not name:
                continue
            category = CATEGORY_OF[prefix]
            if category is None:
                (result.exclude if negate else result.include).append(name)
            else:
                result.scoped.append(ScopedTag(name, category, negate))
        elif prefix == "pages":
            parsed = _parse_num(body)
            if parsed:
                result.pages = parsed
        elif prefix == "favorites":
            parsed = _parse_num(body)
            if parsed:
                result.favorites = parsed
        elif prefix == "uploaded":
            parsed = _parse_date(body)
            if parsed:
                result.uploaded = parsed
        elif prefix == "title":
            if unquoted:
                title_parts.append(unquoted)
        elif prefix == "jtitle":
            if unquoted:
                jtitle_parts.append(unquoted)
        else:
            name = normalize_tag(unquoted)
            if name:
                (result.exclude if negate else result.include).append(name)

    result.title = " ".join(title_parts)
    result.jtitle = " ".join(jtitle_parts)
    return result
