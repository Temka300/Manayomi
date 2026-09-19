"""Explicit, bounded KRDICT lookups with a disposable local response cache."""
from __future__ import annotations

import hashlib
import json
import sqlite3
from typing import Any
from urllib import error, parse, request


KRDICT_ENDPOINT = "https://krdict.korean.go.kr/api/search"
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
LANGUAGES = {"en": "1", "mn": "6"}


class DictionaryLookupError(RuntimeError):
    pass


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _parse_entries(payload: dict[str, Any], language: str) -> list[dict[str, Any]]:
    channel = payload.get("channel") if isinstance(payload, dict) else None
    items = _as_list(channel.get("item") if isinstance(channel, dict) else None)
    entries: list[dict[str, Any]] = []
    for item in items[:20]:
        if not isinstance(item, dict):
            continue
        word = str(item.get("word") or "").strip()
        part_of_speech = str(item.get("pos") or "").strip()
        for sense in _as_list(item.get("sense"))[:10]:
            if not isinstance(sense, dict):
                continue
            translations = _as_list(sense.get("translation"))
            translated = next(
                (
                    translation
                    for translation in translations
                    if isinstance(translation, dict)
                    and (
                        translation.get("trans_dfn")
                        or translation.get("trans_word")
                    )
                ),
                {},
            )
            definition = str(
                translated.get("trans_dfn")
                or translated.get("trans_word")
                or sense.get("definition")
                or ""
            ).strip()
            translated_word = str(translated.get("trans_word") or "").strip()
            if not definition and not translated_word:
                continue
            entries.append(
                {
                    "word": word,
                    "part_of_speech": part_of_speech,
                    "language": language,
                    "translated_word": translated_word,
                    "definition": definition,
                    "sense_order": sense.get("order"),
                    "target_code": sense.get("target_code"),
                }
            )
    return entries


def _remote_lookup(
    *,
    query: str,
    language: str,
    api_key: str,
    user_agent: str,
) -> list[dict[str, Any]]:
    parameters = parse.urlencode(
        {
            "key": api_key,
            "q": query,
            "translated": "y",
            "trans_lang": LANGUAGES[language],
            "sort": "dict",
            "num": "20",
            "part": "word",
            "format": "json",
        }
    )
    outbound = request.Request(
        f"{KRDICT_ENDPOINT}?{parameters}",
        headers={
            "Accept": "application/json",
            "User-Agent": user_agent,
        },
        method="GET",
    )
    try:
        with request.urlopen(outbound, timeout=8) as response:
            final = parse.urlparse(response.geturl())
            if final.scheme != "https" or final.hostname != "krdict.korean.go.kr":
                raise DictionaryLookupError("KRDICT redirected outside its official host")
            declared = response.headers.get("Content-Length")
            if declared and int(declared) > MAX_RESPONSE_BYTES:
                raise DictionaryLookupError("KRDICT response exceeded the 2 MiB limit")
            body = response.read(MAX_RESPONSE_BYTES + 1)
    except (error.URLError, TimeoutError, OSError) as exc:
        raise DictionaryLookupError("KRDICT is unavailable right now") from exc
    if len(body) > MAX_RESPONSE_BYTES:
        raise DictionaryLookupError("KRDICT response exceeded the 2 MiB limit")
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DictionaryLookupError("KRDICT returned an unreadable response") from exc
    return _parse_entries(payload, language)


def lookup(
    catalog_connection: sqlite3.Connection,
    *,
    query: str,
    api_key: str,
    user_agent: str,
) -> dict[str, Any]:
    word = query.strip()
    if not word:
        raise ValueError("Dictionary lookup needs a Korean word")
    if len(word) > 100:
        raise ValueError("Dictionary lookup is limited to 100 characters")
    entries: list[dict[str, Any]] = []
    cache_hits = 0
    for language in ("en", "mn"):
        cache_key = hashlib.sha256(
            f"krdict\0{language}\0{word.casefold()}".encode("utf-8")
        ).hexdigest()
        cached = catalog_connection.execute(
            "SELECT response_json FROM language_dictionary_cache WHERE cache_key=?",
            (cache_key,),
        ).fetchone()
        language_entries: list[dict[str, Any]]
        if cached is not None:
            try:
                language_entries = json.loads(str(cached["response_json"]))
                cache_hits += 1
            except (json.JSONDecodeError, TypeError):
                language_entries = _remote_lookup(
                    query=word,
                    language=language,
                    api_key=api_key,
                    user_agent=user_agent,
                )
        else:
            language_entries = _remote_lookup(
                query=word,
                language=language,
                api_key=api_key,
                user_agent=user_agent,
            )
        catalog_connection.execute(
            "INSERT OR REPLACE INTO language_dictionary_cache"
            "(cache_key, provider, query, response_json, fetched_at) "
            "VALUES (?, 'KRDICT', ?, ?, datetime('now'))",
            (
                cache_key,
                word,
                json.dumps(language_entries, ensure_ascii=False, sort_keys=True),
            ),
        )
        entries.extend(language_entries)
    catalog_connection.commit()
    return {
        "format": "keivotos-language-dictionary-v1",
        "query": word,
        "provider": "KRDICT",
        "provenance": "Explicit network lookup",
        "cached": cache_hits == len(LANGUAGES),
        "entries": entries,
    }
