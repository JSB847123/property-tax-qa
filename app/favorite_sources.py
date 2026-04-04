from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any


TRUTHY_VALUES = {"1", "true", "yes", "y", "on"}


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _coerce_private_flag(source: Mapping[str, Any]) -> bool:
    if "is_private" in source:
        value = source.get("is_private")
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        return _as_text(value).lower() in TRUTHY_VALUES
    return _as_text(source.get("visibility")).lower() == "private"


def build_favorite_id(source: Mapping[str, Any]) -> str:
    is_private = _coerce_private_flag(source)
    category = _as_text(source.get("category") or source.get("source_type")) or "unknown"
    source_type = _as_text(source.get("source_type") or source.get("category")) or category

    if is_private:
        primary_key = _as_text(source.get("id")) or _as_text(source.get("reference"))
    else:
        primary_key = _as_text(source.get("detail_link")) or _as_text(source.get("reference")) or _as_text(source.get("id"))

    fallback_key = {
        "title": _as_text(source.get("title")),
        "source": _as_text(source.get("source")),
        "date": _as_text(source.get("date")),
    }
    fingerprint = {
        "visibility": "private" if is_private else "public",
        "category": category,
        "source_type": source_type,
        "primary_key": primary_key,
        "fallback_key": fallback_key,
    }
    digest = hashlib.sha1(json.dumps(fingerprint, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()[:24]
    return f"fav_{digest}"


def normalize_favorite_source(source: Mapping[str, Any]) -> dict[str, Any]:
    is_private = _coerce_private_flag(source)
    category = _as_text(source.get("category") or source.get("source_type")) or "unknown"
    source_type = _as_text(source.get("source_type") or category) or category

    normalized = {
        "id": _as_text(source.get("id")) or None,
        "category": category,
        "source_type": source_type,
        "is_private": is_private,
        "title": _as_text(source.get("title")) or ("제목 정보 없음" if is_private else "공개자료"),
        "source": _as_text(source.get("source")) or ("등록 자료" if is_private else "국가법령정보센터"),
        "reference": _as_text(source.get("reference")) or None,
        "citation": _as_text(source.get("citation")) or None,
        "detail_link": _as_text(source.get("detail_link")) or None,
        "summary": _as_text(source.get("summary")) or None,
        "date": _as_text(source.get("date")) or None,
    }
    normalized["favorite_id"] = build_favorite_id(normalized)
    return normalized
