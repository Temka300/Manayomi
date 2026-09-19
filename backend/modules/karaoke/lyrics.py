"""Normalize upstream lyric cues while preserving their source representation."""
from __future__ import annotations

import ast
import html
import json
import re
from typing import Any


ASS_OVERRIDE_RE = re.compile(r"\{[^{}]*\}")
SRT_BLOCK_RE = re.compile(
    r"(?:^|\n)(?:\d+\s*\n)?"
    r"(?P<start>\d{1,2}:\d{2}:\d{2}[,.]\d{3})\s*-->\s*"
    r"(?P<end>\d{1,2}:\d{2}:\d{2}[,.]\d{3})[^\n]*\n"
    r"(?P<text>.*?)(?=\n{2,}|\Z)",
    re.DOTALL,
)
VTT_BLOCK_RE = re.compile(
    r"(?:^|\n)(?:[^\n]*\n)?"
    r"(?P<start>\d{2}:\d{2}(?::\d{2})?\.\d{3})\s*-->\s*"
    r"(?P<end>\d{2}:\d{2}(?::\d{2})?\.\d{3})[^\n]*\n"
    r"(?P<text>.*?)(?=\n{2,}|\Z)",
    re.DOTALL,
)
LRC_RE = re.compile(r"^\[(?P<minute>\d+):(?P<second>\d{2})(?:[.:](?P<fraction>\d{1,3}))?\](?P<text>.*)$")


def _seconds(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return max(0.0, float(value))
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip().replace(",", ".")
    try:
        if ":" not in text:
            return max(0.0, float(text))
        parts = [float(part) for part in text.split(":")]
        total = 0.0
        for part in parts:
            total = total * 60 + part
        return max(0.0, total)
    except ValueError:
        return None


def _plain_value(value: Any) -> str:
    if isinstance(value, str):
        stripped = value.strip()
        # Older Kara.moe captures preserved token arrays after an upstream
        # client had converted them to a Python-style repr. Decode that
        # representation only when it has the narrow token-array shape; this
        # is a read-time compatibility path and never rewrites preserved data.
        if (
            len(stripped) <= 200_000
            and stripped.startswith(("[{", "{"))
            and ("'text'" in stripped or '"text"' in stripped)
        ):
            parsed: Any = None
            try:
                parsed = json.loads(stripped)
            except (TypeError, ValueError):
                try:
                    parsed = ast.literal_eval(stripped)
                except (SyntaxError, ValueError):
                    parsed = None
            if isinstance(parsed, (list, dict)):
                return _plain_value(parsed)
        return value
    if isinstance(value, list):
        # Kara.moe may represent one visible lyric line as token objects such
        # as [{"text": "My "}, {"text": "line"}]. Preserve token spacing and
        # discard drawing/tag metadata instead of stringifying the JSON.
        return "".join(_plain_value(part) for part in value)
    elif isinstance(value, dict):
        for key in ("text", "fullText", "line", "lyrics", "content", "value"):
            if key in value:
                return _plain_value(value.get(key))
        return ""
    return str(value or "")


def plain_text(value: Any) -> str:
    text = html.unescape(_plain_value(value))
    text = ASS_OVERRIDE_RE.sub("", text)
    text = text.replace("\\N", "\n").replace("\\n", "\n").strip()
    return text


def _entries(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [entry for entry in value if isinstance(entry, dict)]
    if isinstance(value, dict):
        for key in ("lines", "cues", "lyrics", "content"):
            nested = value.get(key)
            if isinstance(nested, list):
                return [entry for entry in nested if isinstance(entry, dict)]
    return []


def normalize_cues(value: Any) -> list[dict[str, Any]]:
    cues: list[dict[str, Any]] = []
    last_end = 0.0
    for index, entry in enumerate(_entries(value)):
        start = next(
            (
                parsed
                for key in ("start", "start_time", "startTime", "timestamp")
                if (parsed := _seconds(entry.get(key))) is not None
            ),
            None,
        )
        end = next(
            (
                parsed
                for key in ("end", "end_time", "endTime")
                if (parsed := _seconds(entry.get(key))) is not None
            ),
            None,
        )
        duration = _seconds(entry.get("duration"))
        if start is None:
            start = last_end
        if end is None:
            end = start + (duration if duration is not None else 4.0)
        if end <= start:
            end = start + 0.25
        raw = next(
            (
                entry[key]
                for key in ("fullText", "text", "line", "lyrics")
                if entry.get(key) is not None
            ),
            "",
        )
        text = plain_text(raw)
        if not text:
            continue
        cue = {
            "index": index,
            "start": round(start, 3),
            "end": round(end, 3),
            "text": text,
            "raw": (
                raw
                if isinstance(raw, str)
                else json.dumps(raw, ensure_ascii=False, separators=(",", ":"))
            ),
        }
        for key in ("language", "translation", "romaji"):
            if entry.get(key):
                cue[key] = plain_text(entry[key])
        cues.append(cue)
        last_end = end
    return cues


def _vtt_time(seconds: float) -> str:
    milliseconds = round(max(0.0, seconds) * 1000)
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    whole, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{whole:02d}.{millis:03d}"


def to_webvtt(cues: list[dict[str, Any]]) -> str:
    blocks = ["WEBVTT", ""]
    for index, cue in enumerate(cues, start=1):
        blocks.extend(
            [
                str(index),
                f"{_vtt_time(float(cue['start']))} --> "
                f"{_vtt_time(float(cue['end']))}",
                str(cue["text"]),
                "",
            ]
        )
    return "\n".join(blocks)


def to_lrc(cues: list[dict[str, Any]]) -> str:
    lines = ["[re:Keivotos generated from Kara.moe normalized timing]"]
    for cue in cues:
        centiseconds = round(max(0.0, float(cue["start"])) * 100)
        minutes, remainder = divmod(centiseconds, 6000)
        seconds, fraction = divmod(remainder, 100)
        text = str(cue["text"]).replace("\n", " / ")
        lines.append(f"[{minutes:02d}:{seconds:02d}.{fraction:02d}]{text}")
    return "\n".join(lines) + "\n"


def parse_subtitle_text(value: str, format_name: str) -> list[dict[str, Any]]:
    format_name = format_name.casefold().lstrip(".")
    if format_name in {"srt", "vtt"}:
        pattern = SRT_BLOCK_RE if format_name == "srt" else VTT_BLOCK_RE
        cues = []
        for index, match in enumerate(pattern.finditer(value)):
            start = _seconds(match.group("start"))
            end = _seconds(match.group("end"))
            text = plain_text(re.sub(r"<[^>]+>", "", match.group("text")))
            if start is None or end is None or not text:
                continue
            cues.append(
                {
                    "index": index,
                    "start": round(start, 3),
                    "end": round(max(end, start + 0.25), 3),
                    "text": text,
                    "raw": match.group("text").strip(),
                }
            )
        return cues
    if format_name == "lrc":
        cues = []
        pending: list[tuple[float, str]] = []
        for line in value.splitlines():
            match = LRC_RE.match(line.strip())
            if not match or not match.group("text").strip():
                continue
            fraction = match.group("fraction") or "0"
            divisor = 10 ** len(fraction)
            start = (
                int(match.group("minute")) * 60
                + int(match.group("second"))
                + int(fraction) / divisor
            )
            pending.append((start, plain_text(match.group("text"))))
        for index, (start, text) in enumerate(pending):
            end = pending[index + 1][0] if index + 1 < len(pending) else start + 4
            cues.append(
                {
                    "index": index,
                    "start": round(start, 3),
                    "end": round(max(end, start + 0.25), 3),
                    "text": text,
                    "raw": text,
                }
            )
        return cues
    if format_name in {"ass", "ssa"}:
        cues = []
        for line in value.splitlines():
            if not line.startswith("Dialogue:"):
                continue
            parts = line.split(",", 9)
            if len(parts) != 10:
                continue
            start = _seconds(parts[1])
            end = _seconds(parts[2])
            text = plain_text(parts[9])
            if start is None or end is None or not text:
                continue
            cues.append(
                {
                    "index": len(cues),
                    "start": round(start, 3),
                    "end": round(max(end, start + 0.25), 3),
                    "text": text,
                    "raw": parts[9],
                }
            )
        return cues
    return []
