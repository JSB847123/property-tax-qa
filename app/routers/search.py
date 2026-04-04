from __future__ import annotations

import asyncio
import logging
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query, status

from app.query_rules import extract_exact_phrases, filter_results_by_exact_phrases, strip_exact_phrase_quotes
from app.rag import _search_public_results
from app.private_store import StorageError, search_similar


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/search", tags=["search"])

PRIVATE_TOP_K = 5
PUBLIC_CATEGORIES = {"precedent", "tribunal", "statute"}
PRIVATE_EXACT_MATCH_FIELDS = ("title", "source", "content", "practical", "tags")


def _format_date(value: str | None) -> str | None:
    raw = (value or "").strip()
    if not raw:
        return None
    if len(raw) == 8 and raw.isdigit():
        return f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}"
    return raw


def _public_title(item: dict[str, Any]) -> str:
    source_type = item.get("source_type")
    if source_type == "precedent":
        case_name = item.get("title") or item.get("case_name") or ""
        if case_name and case_name != "판례":
            return case_name
        court_name = item.get("court_name") or ""
        case_no = item.get("case_no") or ""
        if court_name and case_no:
            return f"{court_name} {case_no}"
        return case_no or case_name or "판례"
    if source_type == "statute":
        return item.get("title") or item.get("name_kr") or item.get("short_name") or "법령"
    return item.get("title") or item.get("case_name") or item.get("case_no") or "심판례"


def _public_source(item: dict[str, Any]) -> str:
    source_type = item.get("source_type")
    if source_type == "precedent":
        parts = [item.get("court_name") or "", _format_date(item.get("decision_date")) or ""]
        return " ".join(part for part in parts if part).strip() or "국가법령정보센터"
    if source_type == "statute":
        parts = [item.get("ministry") or "", _format_date(item.get("promulgation_date")) or ""]
        return " ".join(part for part in parts if part).strip() or "국가법령정보센터"
    parts = [item.get("agency") or item.get("tribunal_name") or "", _format_date(item.get("decision_date")) or ""]
    return " ".join(part for part in parts if part).strip() or "국가법령정보센터"


def _normalize_private_result(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": item.get("id"),
        "title": item.get("title") or "",
        "source": item.get("source") or "등록 자료",
        "category": item.get("category") or "",
        "is_private": True,
        "date": item.get("date"),
        "content": item.get("content") or "",
        "practical": item.get("practical"),
        "tags": item.get("tags") or [],
        "distance": item.get("distance"),
    }


def _normalize_public_result(item: dict[str, Any]) -> dict[str, Any]:
    source_type = item.get("source_type") or ""
    date_value = (
        item.get("decision_date")
        or item.get("promulgation_date")
        or item.get("effective_date")
        or item.get("disposition_date")
    )
    snippet = item.get("summary") or item.get("holding") or item.get("decision_type") or item.get("short_name") or ""

    return {
        "id": item.get("id") or item.get("serial_no") or item.get("mst") or item.get("law_id"),
        "title": _public_title(item),
        "source": _public_source(item),
        "category": source_type,
        "is_private": False,
        "date": _format_date(date_value),
        "content": snippet,
        "detail_link": item.get("detail_link"),
        "reference": item.get("case_no") or item.get("mst") or item.get("law_id") or item.get("serial_no"),
    }


async def _search_private(question: str, category: str | None) -> list[dict[str, Any]]:
    exact_phrases = extract_exact_phrases(question)
    search_query = strip_exact_phrase_quotes(question).strip() or question.strip()
    results = await asyncio.to_thread(search_similar, search_query, category, PRIVATE_TOP_K)
    normalized = [_normalize_private_result(item) for item in results]
    return filter_results_by_exact_phrases(normalized, exact_phrases, PRIVATE_EXACT_MATCH_FIELDS)


async def _search_public(question: str, category: str | None) -> list[dict[str, Any]]:
    normalized_category = (category or "").strip()

    if normalized_category and normalized_category not in PUBLIC_CATEGORIES:
        return []

    results = await _search_public_results(question)
    if normalized_category:
        results = [item for item in results if item.get("source_type") == normalized_category]
    return [_normalize_public_result(item) for item in results]


@router.get("")
async def integrated_search(
    q: str = Query(..., min_length=1),
    category: str | None = Query(default=None),
    source: Literal["public", "private", "all"] = Query(default="all"),
) -> dict[str, Any]:
    query = q.strip()
    normalized_category = category.strip() if category else None

    private_results: list[dict[str, Any]] = []
    public_results: list[dict[str, Any]] = []

    if source in {"private", "all"}:
        try:
            private_results = await _search_private(query, normalized_category)
        except StorageError as exc:
            if source == "private":
                raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
            logger.warning("Private search skipped due to storage error: %s", exc)
        except Exception as exc:  # pragma: no cover - defensive fallback
            if source == "private":
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="비공개 검색 중 오류가 발생했습니다.") from exc
            logger.exception("Private search failed: %s", exc)

    if source in {"public", "all"}:
        try:
            public_results = await _search_public(query, normalized_category)
        except Exception as exc:  # pragma: no cover - defensive fallback
            if source == "public":
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="공개 검색 중 오류가 발생했습니다.") from exc
            logger.exception("Public search failed: %s", exc)

    results = [*private_results, *public_results]
    return {"results": results, "total": len(results)}
