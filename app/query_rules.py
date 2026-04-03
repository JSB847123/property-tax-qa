from __future__ import annotations

import re
from typing import Any, Iterable

EXACT_PHRASE_PATTERN = re.compile(r'["“”]([^"“”]+)["“”]')


def normalize_match_text(value: str | None) -> str:
    return " ".join((value or "").split()).casefold()


def extract_exact_phrases(query: str) -> list[str]:
    phrases: list[str] = []
    seen: set[str] = set()
    for match in EXACT_PHRASE_PATTERN.finditer(query or ""):
        phrase = " ".join(match.group(1).split())
        key = phrase.casefold()
        if phrase and key not in seen:
            phrases.append(phrase)
            seen.add(key)
    return phrases


def strip_exact_phrase_quotes(query: str) -> str:
    normalized = (query or "").replace("“", '"').replace("”", '"')
    return normalized.replace('"', ' ')


def _combined_item_text(item: dict[str, Any], field_names: Iterable[str]) -> str:
    parts: list[str] = []
    for field_name in field_names:
        value = item.get(field_name)
        if value is None:
            continue
        if isinstance(value, list):
            parts.extend(str(part) for part in value if str(part).strip())
            continue
        parts.append(str(value))
    return normalize_match_text(" ".join(parts))


def matches_exact_phrases(item: dict[str, Any], exact_phrases: list[str], field_names: Iterable[str]) -> bool:
    if not exact_phrases:
        return True
    searchable_text = _combined_item_text(item, field_names)
    if not searchable_text:
        return False
    return all(normalize_match_text(phrase) in searchable_text for phrase in exact_phrases)


def filter_results_by_exact_phrases(
    results: list[dict[str, Any]],
    exact_phrases: list[str],
    field_names: Iterable[str],
) -> list[dict[str, Any]]:
    if not exact_phrases:
        return list(results)
    return [item for item in results if matches_exact_phrases(item, exact_phrases, field_names)]
