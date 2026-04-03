from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, status

from app.favorite_sources import build_favorite_id
from app.models import ChatRequest, ChatResponse
from app.rag import RAGError, generate_answer


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])


def _normalize_source_item(item: dict[str, Any]) -> dict[str, Any]:
    normalized = {
        "id": item.get("id"),
        "citation": item.get("citation"),
        "title": item.get("title") or "",
        "source": item.get("source") or "",
        "category": item.get("category") or item.get("source_type") or "",
        "source_type": item.get("source_type") or item.get("category") or "",
        "reference": item.get("reference"),
        "detail_link": item.get("detail_link"),
        "summary": item.get("summary") or "",
        "is_private": bool(item.get("is_private")) if "is_private" in item else item.get("visibility") == "private",
        "date": item.get("date"),
    }
    normalized["favorite_id"] = build_favorite_id(normalized)
    return normalized


@router.post("", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    try:
        result = await generate_answer(
            question=request.question,
            include_public=request.include_public,
        )
    except RAGError as exc:
        detail = str(exc)
        status_code = status.HTTP_503_SERVICE_UNAVAILABLE if any(
            token in detail.lower() for token in ("api key", "패키지", "설정", "install")
        ) else status.HTTP_500_INTERNAL_SERVER_ERROR
        raise HTTPException(status_code=status_code, detail=detail) from exc
    except Exception as exc:  # pragma: no cover - defensive fallback
        logger.exception("Chat route failed: %s", exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="답변 생성 중 오류가 발생했습니다.") from exc

    normalized_sources = [_normalize_source_item(item) for item in result.sources]
    return ChatResponse(answer=result.answer, sources=normalized_sources)
