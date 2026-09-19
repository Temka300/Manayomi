"""Local Korean morphology and explainable grammar analysis powered by Kiwi."""
from __future__ import annotations

from importlib import metadata
import hashlib
import json
import sqlite3
import threading
from typing import Any


MAX_TEXT_LENGTH = 5000
ANALYZER_SCHEMA_VERSION = 2
_KIWI: Any | None = None
_KIWI_LOCK = threading.Lock()


POS_LABELS = {
    "NNG": ("Common noun", "noun"),
    "NNP": ("Proper noun", "noun"),
    "NNB": ("Dependent noun", "noun"),
    "NR": ("Number", "noun"),
    "NP": ("Pronoun", "noun"),
    "VV": ("Action verb", "verb"),
    "VA": ("Descriptive verb", "adjective"),
    "VX": ("Auxiliary verb", "verb"),
    "VCP": ("Copula", "verb"),
    "VCN": ("Negative copula", "verb"),
    "MM": ("Determiner", "modifier"),
    "MAG": ("Adverb", "modifier"),
    "MAJ": ("Conjunctive adverb", "modifier"),
    "IC": ("Interjection", "other"),
    "JKS": ("Subject particle", "particle"),
    "JKC": ("Complement particle", "particle"),
    "JKG": ("Possessive particle", "particle"),
    "JKO": ("Object particle", "particle"),
    "JKB": ("Adverbial particle", "particle"),
    "JKV": ("Vocative particle", "particle"),
    "JKQ": ("Quotation particle", "particle"),
    "JX": ("Auxiliary particle", "particle"),
    "JC": ("Connecting particle", "particle"),
    "EP": ("Pre-final ending", "ending"),
    "EF": ("Final ending", "ending"),
    "EC": ("Connecting ending", "ending"),
    "ETN": ("Nominalizing ending", "ending"),
    "ETM": ("Adnominal ending", "ending"),
    "XPN": ("Prefix", "affix"),
    "XSN": ("Noun-forming suffix", "affix"),
    "XSV": ("Verb-forming suffix", "affix"),
    "XSA": ("Adjective-forming suffix", "affix"),
    "XR": ("Word root", "affix"),
    "SN": ("Number", "noun"),
    "SL": ("Foreign word", "noun"),
    "SH": ("Chinese character", "noun"),
    "SF": ("Sentence punctuation", "punctuation"),
    "SP": ("Punctuation", "punctuation"),
    "SS": ("Bracket or quote", "punctuation"),
    "SSO": ("Opening bracket or quote", "punctuation"),
    "SSC": ("Closing bracket or quote", "punctuation"),
    "SE": ("Ellipsis", "punctuation"),
    "SO": ("Symbol", "punctuation"),
    "SW": ("Symbol", "punctuation"),
}


PARTICLE_RULES = {
    ("JKS", "이"): ("subject-particle", "이/가", "Subject marker", "Marks the noun that performs or experiences the predicate."),
    ("JKS", "가"): ("subject-particle", "이/가", "Subject marker", "Marks the noun that performs or experiences the predicate."),
    ("JKO", "을"): ("object-particle", "을/를", "Object marker", "Marks the noun directly affected by an action verb."),
    ("JKO", "를"): ("object-particle", "을/를", "Object marker", "Marks the noun directly affected by an action verb."),
    ("JX", "은"): ("topic-particle", "은/는", "Topic or contrast", "Sets the topic and can contrast it with another possibility."),
    ("JX", "는"): ("topic-particle", "은/는", "Topic or contrast", "Sets the topic and can contrast it with another possibility."),
    ("JX", "도"): ("also-particle", "도", "Also / too", "Adds the marked item to an already understood set."),
    ("JKB", "에"): ("place-time-particle", "에", "Place, time, or destination", "Marks a static location, a time, or a destination depending on the predicate."),
    ("JKB", "에서"): ("action-location-particle", "에서", "Action location or origin", "Marks where an action happens, or where movement begins."),
    ("JKB", "보다"): ("comparison-particle", "보다", "Comparison", "Marks the standard used for a comparison: than or compared with."),
    ("JKG", "의"): ("possessive-particle", "의", "Possession or relation", "Connects a noun to another noun in a possessive or descriptive relation."),
}


ENDING_RULES = {
    ("EP", "었"): ("past-tense", "-았/었-", "Past tense", "Places the following predicate before the present reference time."),
    ("EP", "았"): ("past-tense", "-았/었-", "Past tense", "Places the following predicate before the present reference time."),
    ("EP", "였"): ("past-tense", "-았/었-", "Past tense", "Places the following predicate before the present reference time."),
    ("EP", "시"): ("honorific", "-시-", "Subject honorific", "Raises the person who is the subject of the predicate."),
    ("EP", "겠"): ("prospective", "-겠-", "Intention or supposition", "Often presents intention, prediction, or a speaker's inference."),
    ("EC", "고"): ("and-connector", "-고", "And / sequence", "Connects predicates in parallel or chronological order."),
    ("EC", "지만"): ("contrast-connector", "-지만", "But / although", "Connects a statement to a contrasting result."),
    ("EC", "면"): ("conditional", "-(으)면", "If / when", "Makes the first clause a condition for the following clause."),
    ("EC", "려고"): ("intention-connector", "-(으)려고", "In order to / intending to", "Connects an intention or purpose to the next action."),
    ("EC", "는데"): ("background-connector", "-는데", "Background or contrast", "Supplies background, invites a response, or introduces a contrast."),
    ("ETM", "는"): ("present-adnominal", "-는", "Present adnominal form", "Turns an action verb into a modifier for the following noun."),
    ("ETM", "ㄴ"): ("adnominal", "-(으)ㄴ", "Adnominal form", "Turns a predicate into a modifier for the following noun."),
    ("ETM", "은"): ("adnominal", "-(으)ㄴ", "Adnominal form", "Turns a predicate into a modifier for the following noun."),
    ("ETM", "던"): ("retrospective-adnominal", "-던", "Retrospective adnominal form", "Recalls an incomplete, repeated, or remembered past situation while modifying a noun."),
    ("ETN", "기"): ("nominalizer", "-기", "Nominalizer", "Turns a predicate into a noun-like expression."),
}


def _distribution_version(name: str) -> str | None:
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return None


def engine_status() -> dict[str, Any]:
    kiwi_version = _distribution_version("kiwipiepy")
    romanizer_version = _distribution_version("koroman")
    return {
        "available": kiwi_version is not None,
        "engine": "Kiwi",
        "engine_version": kiwi_version,
        "romanizer": "koroman",
        "romanizer_version": romanizer_version,
        "offline": True,
        "max_text_length": MAX_TEXT_LENGTH,
    }


def _get_kiwi() -> Any:
    global _KIWI
    if _KIWI is not None:
        return _KIWI
    with _KIWI_LOCK:
        if _KIWI is None:
            try:
                from kiwipiepy import Kiwi
            except ImportError as exc:
                raise RuntimeError(
                    "The Korean analyzer is unavailable. Install the locked "
                    "kiwipiepy dependency and restart Keivotos."
                ) from exc
            _KIWI = Kiwi()
    return _KIWI


def _romanize(text: str) -> str:
    try:
        from koroman import romanize
    except ImportError:
        return ""
    try:
        return str(romanize(text))
    except (TypeError, ValueError):
        return ""


def _base_tag(tag: str) -> str:
    return tag.split("-", 1)[0]


def _lemma(kiwi: Any, form: str, tag: str) -> str:
    base_tag = _base_tag(tag)
    if base_tag not in {"VV", "VA", "VX", "VCP", "VCN", "XR", "XSV", "XSA"}:
        return form
    try:
        joined = str(kiwi.join([(form, base_tag), ("다", "EF")])).strip()
        return joined or f"{form}다"
    except (AttributeError, TypeError, ValueError):
        return f"{form}다" if not form.endswith("다") else form


def _grammar_rule(tag: str, form: str) -> dict[str, Any] | None:
    base_tag = _base_tag(tag)
    rule = PARTICLE_RULES.get((base_tag, form)) or ENDING_RULES.get((base_tag, form))
    if rule is None and base_tag == "EF":
        rule = (
            f"final-{form}",
            form,
            "Sentence ending",
            "Closes the clause and carries speech level, mood, or sentence type.",
        )
    if rule is None and base_tag == "EC":
        rule = (
            f"connector-{form}",
            form,
            "Connecting ending",
            "Links this predicate to the clause that follows.",
        )
    if rule is None and base_tag in {"XSN", "XSV", "XSA"}:
        labels = {
            "XSN": "Noun-forming suffix",
            "XSV": "Verb-forming suffix",
            "XSA": "Adjective-forming suffix",
        }
        rule = (
            f"{base_tag.casefold()}-{form}",
            form,
            labels[base_tag],
            "Changes the grammatical role of the word it attaches to.",
        )
    if rule is None:
        return None
    rule_id, pattern, title, summary = rule
    return {
        "rule_id": rule_id,
        "pattern": pattern,
        "title": title,
        "summary": summary,
        "category": POS_LABELS.get(base_tag, ("Grammar", "other"))[1],
        "level": "Reference",
        "provenance": "Keivotos rule",
    }


def _token_value(
    kiwi: Any,
    source_text: str,
    raw: Any,
    *,
    sentence_index: int,
    token_index: int,
    group: int,
) -> dict[str, Any]:
    form = str(getattr(raw, "form", ""))
    tag = str(getattr(raw, "tag", ""))
    start = int(getattr(raw, "start", 0))
    length = int(getattr(raw, "len", len(form)))
    end = max(start, start + length)
    original_surface = (
        source_text[start:end]
        if 0 <= start < end <= len(source_text)
        else form
    )
    base_tag = _base_tag(tag)
    pos_label, color_group = POS_LABELS.get(base_tag, (base_tag or "Unknown", "other"))
    return {
        "token_index": token_index,
        "sentence_index": sentence_index,
        "group": group,
        "surface": form or original_surface,
        "original_surface": original_surface,
        "form": form,
        "lemma": _lemma(kiwi, form, tag),
        "tag": tag,
        "pos": pos_label,
        "color_group": color_group,
        "start": start,
        "end": end,
        "romanization": _romanize(original_surface or form),
        "grammar": _grammar_rule(tag, form),
    }


def _analyze_uncached(source_text: str) -> dict[str, Any]:
    kiwi = _get_kiwi()
    raw_sentences = kiwi.split_into_sents(source_text, return_tokens=True)
    sentences: list[dict[str, Any]] = []
    flat_tokens: list[dict[str, Any]] = []
    token_index = 0
    group = 0
    previous_end = 0
    for sentence_index, raw_sentence in enumerate(raw_sentences):
        sentence_start = int(getattr(raw_sentence, "start", 0))
        sentence_end = int(getattr(raw_sentence, "end", sentence_start))
        sentence_text = str(getattr(raw_sentence, "text", ""))
        raw_tokens = list(getattr(raw_sentence, "tokens", ()) or ())
        sentence_tokens: list[dict[str, Any]] = []
        for raw in raw_tokens:
            start = int(getattr(raw, "start", 0))
            if token_index and any(char.isspace() for char in source_text[previous_end:start]):
                group += 1
            value = _token_value(
                kiwi,
                source_text,
                raw,
                sentence_index=sentence_index,
                token_index=token_index,
                group=group,
            )
            sentence_tokens.append(value)
            flat_tokens.append(value)
            token_index += 1
            previous_end = int(value["end"])
        sentences.append(
            {
                "sentence_index": sentence_index,
                "text": sentence_text,
                "start": sentence_start,
                "end": sentence_end,
                "romanization": _romanize(sentence_text),
                "token_indexes": [token["token_index"] for token in sentence_tokens],
            }
        )
        group += 1

    grammar_map: dict[str, dict[str, Any]] = {}
    by_group: dict[int, list[dict[str, Any]]] = {}
    for token in flat_tokens:
        by_group.setdefault(int(token["group"]), []).append(token)
    for group_tokens in by_group.values():
        core: list[dict[str, Any]] = []
        for token in group_tokens:
            if _base_tag(str(token["tag"])) in {
                "EP", "EF", "EC", "ETM", "ETN",
                "JKS", "JKC", "JKG", "JKO", "JKB", "JKV", "JKQ", "JX", "JC",
                "SF", "SP", "SS", "SSO", "SSC", "SE", "SO", "SW",
            }:
                break
            core.append(token)
        if not core or not any(
            _base_tag(str(token["tag"]))
            in {"VV", "VA", "VX", "VCP", "VCN", "XSV", "XSA"}
            for token in core
        ):
            continue
        try:
            group_lemma = str(
                kiwi.join(
                    [
                        *[
                            (str(token["form"]), _base_tag(str(token["tag"])))
                            for token in core
                        ],
                        ("다", "EF"),
                    ]
                )
            ).strip()
        except (AttributeError, TypeError, ValueError):
            group_lemma = "".join(str(token["form"]) for token in core) + "다"
        for token in group_tokens:
            if _base_tag(str(token["tag"])) not in {
                "SF", "SP", "SS", "SSO", "SSC", "SE", "SO", "SW",
            }:
                token["group_lemma"] = group_lemma

    for token in flat_tokens:
        grammar = token.get("grammar")
        if not grammar:
            continue
        key = str(grammar["rule_id"])
        if key not in grammar_map:
            grammar_map[key] = {**grammar, "token_indexes": []}
        grammar_map[key]["token_indexes"].append(token["token_index"])

    return {
        "format": "keivotos-language-analysis-v1",
        "text": source_text,
        "romanization": _romanize(source_text),
        "sentences": sentences,
        "tokens": flat_tokens,
        "grammar": list(grammar_map.values()),
        "engine": {
            "name": "Kiwi",
            "version": _distribution_version("kiwipiepy"),
            "provenance": "Local morphology",
        },
    }


def analyze(
    catalog_connection: sqlite3.Connection,
    source_text: str,
) -> tuple[dict[str, Any], bool]:
    text = source_text.strip()
    if not text:
        raise ValueError("Enter Korean text to analyze")
    if len(text) > MAX_TEXT_LENGTH:
        raise ValueError(f"Analyzer text cannot exceed {MAX_TEXT_LENGTH:,} characters")
    version = _distribution_version("kiwipiepy") or "unavailable"
    cache_key = hashlib.sha256(
        f"{ANALYZER_SCHEMA_VERSION}\0{version}\0{text}".encode("utf-8")
    ).hexdigest()
    cached = catalog_connection.execute(
        "SELECT result_json FROM language_analysis_cache WHERE cache_key=?",
        (cache_key,),
    ).fetchone()
    if cached is not None:
        try:
            return json.loads(str(cached["result_json"])), True
        except (json.JSONDecodeError, TypeError):
            pass
    result = _analyze_uncached(text)
    catalog_connection.execute(
        "INSERT OR REPLACE INTO language_analysis_cache"
        "(cache_key, source_text, engine_version, result_json, created_at) "
        "VALUES (?, ?, ?, ?, datetime('now'))",
        (
            cache_key,
            text,
            version,
            json.dumps(result, ensure_ascii=False, sort_keys=True),
        ),
    )
    catalog_connection.commit()
    return result, False
