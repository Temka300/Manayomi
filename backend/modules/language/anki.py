"""Strict read-only AnkiConnect client and KO1Kv2 field normalization."""
from __future__ import annotations

from html import unescape
from html.parser import HTMLParser
import json
import re
import socket
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


API_VERSION = 6
DEFAULT_PORT = 8765
MAX_RESPONSE_BYTES = 32 * 1024 * 1024
READ_ACTIONS = frozenset(
    {
        "requestPermission",
        "version",
        "deckNames",
        "modelNames",
        "modelFieldNames",
        "findNotes",
        "notesModTime",
        "notesInfo",
        "cardsInfo",
        "findCards",
        "getReviewsOfCards",
        "getMediaDirPath",
        "retrieveMediaFile",
    }
)

DEFAULT_KO1K_PROFILE = {
    "note_type": "KO1Kv2",
    "map": {
        "Word": "headword",
        "Word in Sentence Form": "sentence_form",
        "Definition": "sense_block",
        "Example Sentence": "example",
        "Sentence Translation": "example_translation_block",
        "Word Audio": "word_audio",
        "Sentence Audio": "sentence_audio",
        "Image": "image",
        "Grammar Notes": "grammar",
        "Pronunciation": "reading",
        "Index": "sort_index",
    },
    "sense_languages": ["en", "mn"],
}

KO1K_PROFILE_FIELDS = frozenset(DEFAULT_KO1K_PROFILE["map"])

SOUND_RE = re.compile(r"\[sound:([^\]\r\n]+)\]", re.IGNORECASE)
IMAGE_RE = re.compile(
    r"<img\b[^>]*?\bsrc\s*=\s*(?:\"([^\"]+)\"|'([^']+)'|([^\s>]+))",
    re.IGNORECASE,
)
HANGUL_RE = re.compile(r"[\u1100-\u11ff\u3130-\u318f\uac00-\ud7af]")
CYRILLIC_RE = re.compile(r"[\u0400-\u04ff]")
LATIN_RE = re.compile(r"[A-Za-z]")


class AnkiConnectError(RuntimeError):
    pass


def proposed_ko1k_profile(
    note_type: str,
    field_names: list[str],
) -> dict[str, Any] | None:
    """Return the built-in mapping for field-compatible KO1Kv2 variants."""
    compact_name = re.sub(r"[\s_-]+", "", note_type).casefold()
    available_fields = {
        str(field_name).strip()
        for field_name in field_names
        if str(field_name).strip()
    }
    if not compact_name.startswith("ko1kv2"):
        return None
    if not KO1K_PROFILE_FIELDS.issubset(available_fields):
        return None
    return {
        **DEFAULT_KO1K_PROFILE,
        "note_type": note_type,
        "map": dict(DEFAULT_KO1K_PROFILE["map"]),
        "sense_languages": list(DEFAULT_KO1K_PROFILE["sense_languages"]),
    }


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        if tag.casefold() in {"br", "div", "p", "li"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() in {"div", "p", "li"}:
            self.parts.append("\n")


def text_value(value: Any) -> str:
    if isinstance(value, dict):
        value = value.get("value", "")
    parser = _TextExtractor()
    try:
        parser.feed(str(value or ""))
    except Exception:
        return unescape(str(value or "")).strip()
    return unescape("".join(parser.parts)).strip()


def script_language(value: str) -> str:
    if HANGUL_RE.search(value):
        return "ko"
    if CYRILLIC_RE.search(value):
        return "mn"
    if LATIN_RE.search(value):
        return "en"
    return "und"


def split_language_block(
    value: str,
    expected_languages: list[str],
) -> list[dict[str, str]]:
    lines = [
        line.strip()
        for line in re.split(r"(?:\r?\n)+", text_value(value))
        if line.strip()
    ]
    result: list[dict[str, str]] = []
    for position, line in enumerate(lines):
        expected = (
            expected_languages[position]
            if position < len(expected_languages)
            else "und"
        )
        detected = script_language(line)
        language = detected if detected != "und" else expected
        if expected != "und" and detected not in {"und", expected}:
            language = detected
        result.append({"lang": language, "text": line})
    return result


def extract_media_filenames(value: Any) -> list[str]:
    raw = str(value.get("value", "") if isinstance(value, dict) else value or "")
    names = [unescape(match).strip() for match in SOUND_RE.findall(raw)]
    for match in IMAGE_RE.findall(raw):
        name = next((part for part in match if part), "")
        if name:
            names.append(unescape(name).strip())
    return list(dict.fromkeys(name for name in names if name))


def normalize_note(
    note: dict[str, Any],
    profile: dict[str, Any],
) -> dict[str, Any]:
    fields = note.get("fields") if isinstance(note.get("fields"), dict) else {}
    mapping = profile.get("map") if isinstance(profile.get("map"), dict) else {}
    languages = [
        str(value)
        for value in profile.get("sense_languages", ["en", "mn"])
    ]
    canonical: dict[str, Any] = {}
    media: dict[str, list[str]] = {}
    for field_name, role in mapping.items():
        field_value = fields.get(field_name, "")
        if role in {"word_audio", "sentence_audio", "image"}:
            media[str(role)] = extract_media_filenames(field_value)
        elif str(role).endswith("_block"):
            canonical[str(role)] = split_language_block(
                text_value(field_value),
                languages,
            )
        else:
            canonical[str(role)] = text_value(field_value)
    headword = str(canonical.get("headword") or "").strip()
    if not headword:
        raise AnkiConnectError("Mapped Anki note has no headword")
    try:
        sort_index = int(str(canonical.get("sort_index") or "").strip())
    except ValueError:
        sort_index = None
    senses = canonical.get("sense_block")
    if not isinstance(senses, list):
        senses = []
    translations = canonical.get("example_translation_block")
    if not isinstance(translations, list):
        translations = []
    notes_text = []
    for role, kind in (
        ("grammar", "grammar"),
        ("reading", "pronunciation"),
    ):
        body = str(canonical.get(role) or "").strip()
        if body:
            notes_text.append({"kind": kind, "body": body})
    example = str(canonical.get("example") or "").strip()
    return {
        "source_key": str(note.get("noteId") or ""),
        "anki_mod": note.get("mod"),
        "note_type": str(note.get("modelName") or profile.get("note_type") or ""),
        "lang": "ko",
        "headword": headword,
        "sentence_form": (
            str(canonical.get("sentence_form") or "").strip() or headword
        ),
        "reading": str(canonical.get("reading") or "").strip(),
        "sort_index": sort_index,
        "senses": senses,
        "examples": (
            [{"sentence": example, "translations": translations}]
            if example
            else []
        ),
        "notes_text": notes_text,
        "tags": [str(value) for value in note.get("tags", [])],
        "media_filenames": media,
        "fields": {
            str(name): str(
                value.get("value", "") if isinstance(value, dict) else value
            )
            for name, value in fields.items()
        },
        "card_ids": [str(value) for value in note.get("cards", [])],
    }


class AnkiConnectClient:
    def __init__(
        self,
        *,
        port: int = DEFAULT_PORT,
        api_key: str | None = None,
        timeout: float = 10.0,
    ) -> None:
        if not 1 <= int(port) <= 65535:
            raise ValueError("AnkiConnect port must be between 1 and 65535")
        self.port = int(port)
        self.api_key = api_key.strip() if api_key else None
        self.timeout = max(1.0, min(float(timeout), 60.0))
        self.url = f"http://127.0.0.1:{self.port}/"

    def call(self, action: str, **params: Any) -> Any:
        if action not in READ_ACTIONS:
            raise AnkiConnectError("AnkiConnect action is outside the read-only allowlist")
        payload: dict[str, Any] = {
            "action": action,
            "version": API_VERSION,
            "params": params,
        }
        if self.api_key:
            payload["key"] = self.api_key
        request = Request(
            self.url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "User-Agent": "Keivotos Languages read-only bridge",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                raw = response.read(MAX_RESPONSE_BYTES + 1)
        except (HTTPError, URLError, TimeoutError, socket.timeout, OSError) as exc:
            raise AnkiConnectError(
                "AnkiConnect is unavailable on the configured loopback port"
            ) from exc
        if len(raw) > MAX_RESPONSE_BYTES:
            raise AnkiConnectError("AnkiConnect response exceeded 32 MiB")
        try:
            envelope = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AnkiConnectError("AnkiConnect returned malformed JSON") from exc
        if not isinstance(envelope, dict) or "error" not in envelope:
            raise AnkiConnectError("AnkiConnect returned an unexpected envelope")
        if envelope.get("error"):
            raise AnkiConnectError(str(envelope["error"]))
        return envelope.get("result")

    def probe(self) -> dict[str, Any]:
        permission = self.call("requestPermission")
        version = self.call("version")
        decks = self.call("deckNames")
        return {
            "reachable": True,
            "permission": permission,
            "version": version,
            "decks": decks if isinstance(decks, list) else [],
        }
