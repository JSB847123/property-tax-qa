from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.law_search import get_precedent_detail, get_statute_detail, search_precedents, search_statutes, search_tribunal
from app.llm_client import LLMClientError, generate_text
from app.query_rules import extract_exact_phrases, filter_results_by_exact_phrases, strip_exact_phrase_quotes
from app.models import ChatResponse
from app.private_store import StorageError, search_similar


logger = logging.getLogger(__name__)


LLM_MAX_TOKENS = 1400
PRIVATE_CONTEXT_LIMIT = 5
PRIVATE_SOURCE_LIMIT = 10
PUBLIC_CONTEXT_LIMIT = 5
PUBLIC_SOURCE_LIMIT = 40
PUBLIC_DETAIL_LIMIT = 8

SYSTEM_PROMPT = """
한국 지방세(취득세·재산세) 전문 AI 어시스턴트.

규칙:
1. 제공된 자료만 기반으로 답변
2. [비공개자료N] 또는 [공개자료N] 형태로 인용
3. 없는 내용은 "등록된 자료에서 찾지 못했습니다" 명시
4. 객관적·중립적 어조
5. 답변 구성:
   - 📋 법률 내용 (판례/법령 근거)
   - 🖥️ 전산 처리 방법 (전산적용 정보가 있는 경우)
   - 🗣️ 유사 민원 처리 사례 (민원처리 자료가 있는 경우)
6. 답변 끝에 📌 참조 출처 요약
7. 비공개자료는 "내부자료"로 표시, 공개자료는 판례번호/조문번호 표시
8. 전문가 상담 권고
""".strip()

PRIVATE_CATEGORY_LABELS = {
    "precedent": "판례",
    "tribunal": "심판례",
    "case": "사례",
    "civil": "민원처리",
    "theory": "이론",
    "statute": "법령",
    "other": "기타",
}
PUBLIC_CATEGORY_LABELS = {
    "precedent": "판례",
    "statute": "법령",
    "tribunal": "심판례",
}

PUBLIC_TAX_TERMS = ("취득세", "재산세", "등록면허세")
PUBLIC_QUERY_NOISE_TOKENS = {
    "관련",
    "알려줘",
    "알려주세요",
    "설명해줘",
    "설명해주세요",
    "정리해줘",
    "정리해주세요",
    "찾아줘",
    "찾아주세요",
    "문의",
    "질문",
}
PUBLIC_SOURCE_HINT_TOKENS = {
    "판례",
    "판결",
    "심판례",
    "심판",
    "재결",
    "결정",
    "법령",
    "조문",
    "시행령",
    "시행규칙",
}
PUBLIC_QUERY_REWRITE_MAP = {
    "특수관계인간": ("특수관계인", "특수관계자"),
    "특수관계자간": ("특수관계자", "특수관계인"),
    "부당행위계산부인": ("부당행위계산",),
}
GENERIC_PUBLIC_TITLES = {"판례", "법령", "심판례", "공개자료"}
PRIVATE_EXACT_MATCH_FIELDS = ("title", "source", "content", "practical", "tags")
PUBLIC_EXACT_MATCH_FIELDS = (
    "title",
    "case_name",
    "case_no",
    "court_name",
    "summary",
    "holding",
    "references",
    "short_name",
    "agency",
    "tribunal_name",
    "decision_type",
)


class RAGError(Exception):
    """Raised when the RAG answer generation pipeline cannot complete."""



def _truncate_text(value: str | None, limit: int = 700) -> str:
    text = " ".join((value or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def _format_date(value: str | None) -> str:
    raw = (value or "").strip()
    if len(raw) == 8 and raw.isdigit():
        return f"{raw[:4]}.{raw[4:6]}.{raw[6:8]}."
    if len(raw) == 10 and raw[4] == "-" and raw[7] == "-":
        return f"{raw[:4]}.{raw[5:7]}.{raw[8:10]}."
    return raw


def _private_category_label(category: str | None) -> str:
    return PRIVATE_CATEGORY_LABELS.get((category or "").strip(), category or "기타")


def _public_category_label(source_type: str | None) -> str:
    return PUBLIC_CATEGORY_LABELS.get((source_type or "").strip(), source_type or "공개자료")


def _build_precedent_title(item: dict[str, Any]) -> str:
    case_name = item.get("title") or item.get("case_name") or ""
    if not _is_generic_public_title(case_name):
        return case_name

    court_name = item.get("court_name") or ""
    case_no = item.get("case_no") or ""
    if court_name and case_no:
        return f"{court_name} {case_no}"
    return case_no or case_name or "판례"


def _build_precedent_source(item: dict[str, Any]) -> str:
    parts = [item.get("court_name") or "", _format_date(item.get("decision_date"))]
    return " ".join(part for part in parts if part).strip() or "국가법령정보센터"


def _build_statute_title(item: dict[str, Any]) -> str:
    return item.get("title") or item.get("name_kr") or item.get("short_name") or "법령"


def _build_statute_source(item: dict[str, Any]) -> str:
    ministry = item.get("ministry") or ""
    promulgation_date = _format_date(item.get("promulgation_date"))
    parts = [ministry, promulgation_date]
    return " ".join(part for part in parts if part).strip() or "국가법령정보센터"


def _build_tribunal_title(item: dict[str, Any]) -> str:
    return item.get("title") or item.get("case_name") or item.get("case_no") or "심판례"


def _build_tribunal_source(item: dict[str, Any]) -> str:
    agency = item.get("agency") or item.get("tribunal_name") or ""
    decision_date = _format_date(item.get("decision_date"))
    parts = [agency, decision_date]
    return " ".join(part for part in parts if part).strip() or "국가법령정보센터"


def _is_generic_public_title(value: str | None) -> bool:
    title = (value or "").strip()
    return not title or title in GENERIC_PUBLIC_TITLES


def _build_public_source_summary(item: dict[str, Any]) -> str:
    source_type = item.get("source_type")
    if source_type == "precedent":
        return (
            item.get("summary")
            or item.get("holding")
            or item.get("references")
            or item.get("full_text")
            or (f"사건번호 {item.get('case_no')}" if item.get("case_no") else "")
        )
    if source_type == "statute":
        article_lines = _statute_article_lines(item)
        if article_lines:
            return article_lines[0].removeprefix("- ").strip()
        return item.get("short_name") or item.get("full_text") or ""
    return item.get("decision_type") or item.get("case_no") or item.get("agency") or item.get("tribunal_name") or ""


def _precedent_quality_score(item: dict[str, Any]) -> int:
    title = item.get("title") or item.get("case_name") or ""
    score = 0
    if item.get("summary"):
        score += 6
    if item.get("holding"):
        score += 5
    if item.get("full_text"):
        score += 3
    if item.get("case_no"):
        score += 4
    if not _is_generic_public_title(title):
        score += 3
    if item.get("court_name"):
        score += 1
    if item.get("decision_date"):
        score += 1
    if item.get("detail_link"):
        score += 1
    return score


def _filter_and_sort_precedents(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ranked: list[tuple[int, int, dict[str, Any]]] = []
    for index, item in enumerate(results):
        title = item.get("title") or item.get("case_name") or ""
        has_meaningful_title = not _is_generic_public_title(title)
        has_usable_summary = any(item.get(key) for key in ("summary", "holding", "references", "full_text"))
        has_identifier = bool(item.get("case_no") or item.get("court_name"))
        if not any((has_meaningful_title, has_usable_summary, has_identifier)):
            continue
        ranked.append((_precedent_quality_score(item), index, item))

    ranked.sort(key=lambda pair: (-pair[0], pair[1]))
    return [item for _, _, item in ranked]


def _private_context_block(item: dict[str, Any], index: int) -> str:
    lines = [
        f"[비공개자료{index}] 분류: {_private_category_label(item.get('category'))} | 제목: {item.get('title') or '제목 없음'} | 출처: {item.get('source') or '내부자료'}",
        f"내용: {_truncate_text(item.get('content'), 1200)}",
    ]
    if item.get("practical"):
        lines.append(f"🖥️ 전산적용: {_truncate_text(item.get('practical'), 700)}")
    if item.get("tags"):
        lines.append(f"태그: {', '.join(item.get('tags', []))}")
    if item.get("date"):
        lines.append(f"기준일자: {_format_date(item.get('date')) or item.get('date')}")
    return "\n".join(lines)


def _statute_article_lines(item: dict[str, Any]) -> list[str]:
    articles = item.get("articles") or []
    lines: list[str] = []
    for article in articles[:3]:
        article_no = article.get("article_no") or ""
        article_branch = article.get("article_branch_no") or ""
        article_title = article.get("article_title") or ""
        article_label = f"제{article_no}조"
        if article_branch and article_branch != "0":
            article_label += f"의{article_branch}"
        if article_title:
            article_label += f" ({article_title})"
        article_content = _truncate_text(article.get("article_content"), 320)
        lines.append(f"- {article_label}: {article_content}")
    return lines


def _public_context_block(item: dict[str, Any], index: int) -> str:
    source_type = item.get("source_type")
    category_label = _public_category_label(source_type)

    if source_type == "precedent":
        lines = [
            f"[공개자료{index}] 분류: {category_label} | 제목: {_build_precedent_title(item)} | 출처: {_build_precedent_source(item)}",
        ]
        if item.get("holding"):
            lines.append(f"판시사항: {_truncate_text(item.get('holding'), 500)}")
        if item.get("summary"):
            lines.append(f"판결요지: {_truncate_text(item.get('summary'), 800)}")
        if item.get("references"):
            lines.append(f"참조조문: {_truncate_text(item.get('references'), 400)}")
        if not any(item.get(key) for key in ("holding", "summary", "references")) and item.get("case_no"):
            lines.append(f"사건번호: {item.get('case_no')}")
        return "\n".join(lines)

    if source_type == "statute":
        lines = [
            f"[공개자료{index}] 분류: {category_label} | 제목: {_build_statute_title(item)} | 출처: {_build_statute_source(item)}",
        ]
        article_lines = _statute_article_lines(item)
        if article_lines:
            lines.append("주요조문:")
            lines.extend(article_lines)
        elif item.get("full_text"):
            lines.append(f"조문내용: {_truncate_text(item.get('full_text'), 900)}")
        if item.get("promulgation_no") or item.get("effective_date"):
            lines.append(
                f"공포번호/시행일자: {item.get('promulgation_no') or '-'} / {_format_date(item.get('effective_date')) or item.get('effective_date') or '-'}"
            )
        return "\n".join(lines)

    lines = [
        f"[공개자료{index}] 분류: {category_label} | 제목: {_build_tribunal_title(item)} | 출처: {_build_tribunal_source(item)}",
    ]
    if item.get("case_no"):
        lines.append(f"사건번호: {item.get('case_no')}")
    if item.get("decision_type"):
        lines.append(f"재결구분: {item.get('decision_type')}")
    if item.get("disposition_date"):
        lines.append(f"처분일자: {_format_date(item.get('disposition_date')) or item.get('disposition_date')}")
    if item.get("detail_link"):
        lines.append(f"상세링크: {item.get('detail_link')}")
    return "\n".join(lines)


def _build_source_entry(item: dict[str, Any], index: int, *, visibility: str) -> dict[str, Any]:
    if visibility == "private":
        return {
            "citation": f"[비공개자료{index}]",
            "visibility": "private",
            "display_type": "내부자료",
            "category": item.get("category"),
            "category_label": _private_category_label(item.get("category")),
            "title": item.get("title"),
            "source": item.get("source") or "내부자료",
            "date": item.get("date"),
            "id": item.get("id"),
        }

    source_type = item.get("source_type")
    if source_type == "precedent":
        reference = item.get("case_no") or item.get("serial_no")
        title = _build_precedent_title(item)
        source = _build_precedent_source(item)
    elif source_type == "statute":
        reference = item.get("mst") or item.get("law_id")
        title = _build_statute_title(item)
        source = _build_statute_source(item)
    else:
        reference = item.get("case_no") or item.get("serial_no")
        title = _build_tribunal_title(item)
        source = _build_tribunal_source(item)

    public_summary = _build_public_source_summary(item)
    return {
        "citation": f"[공개자료{index}]",
        "visibility": "public",
        "display_type": _public_category_label(source_type),
        "source_type": source_type,
        "title": title,
        "source": source,
        "reference": reference,
        "detail_link": item.get("detail_link"),
        "summary": _truncate_text(public_summary, 220) if public_summary else None,
    }


def _build_sources(private_results: list[dict[str, Any]], public_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    for index, item in enumerate(private_results, start=1):
        sources.append(_build_source_entry(item, index, visibility="private"))
    for index, item in enumerate(public_results, start=1):
        sources.append(_build_source_entry(item, index, visibility="public"))
    return sources


def _build_context(private_results: list[dict[str, Any]], public_results: list[dict[str, Any]]) -> str:
    blocks: list[str] = []

    for index, item in enumerate(private_results, start=1):
        blocks.append(_private_context_block(item, index))

    for index, item in enumerate(public_results, start=1):
        blocks.append(_public_context_block(item, index))

    return "\n\n".join(blocks).strip() or "등록된 자료에서 찾지 못했습니다."


async def _search_private_results(question: str, *, limit: int = PRIVATE_SOURCE_LIMIT) -> list[dict[str, Any]]:
    try:
        results = await asyncio.to_thread(search_similar, question, None, limit)
        return results[:limit]
    except StorageError as exc:
        logger.warning("Private vector search is unavailable: %s", exc)
        return []
    except Exception as exc:  # pragma: no cover - defensive fallback
        logger.exception("Private search failed: %s", exc)
        return []


async def _enrich_precedents(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates = [item for item in results[:PUBLIC_DETAIL_LIMIT] if item.get("serial_no")]
    if not candidates:
        return results

    detail_responses = await asyncio.gather(
        *(get_precedent_detail(item["serial_no"]) for item in candidates),
        return_exceptions=True,
    )
    detail_map: dict[str, dict[str, Any]] = {}
    for detail in detail_responses:
        if isinstance(detail, Exception):
            logger.warning("Precedent detail lookup failed: %s", detail)
            continue
        serial_no = detail.get("serial_no")
        if serial_no:
            detail_map[serial_no] = detail

    enriched: list[dict[str, Any]] = []
    for item in results:
        detail = detail_map.get(item.get("serial_no", ""), {})
        enriched.append({**item, **detail})
    return enriched


async def _enrich_statutes(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates = [item for item in results[:PUBLIC_DETAIL_LIMIT] if item.get("mst")]
    if not candidates:
        return results

    detail_responses = await asyncio.gather(
        *(get_statute_detail(item["mst"]) for item in candidates),
        return_exceptions=True,
    )
    detail_map: dict[str, dict[str, Any]] = {}
    for detail in detail_responses:
        if isinstance(detail, Exception):
            logger.warning("Statute detail lookup failed: %s", detail)
            continue
        mst = detail.get("mst")
        if mst:
            detail_map[mst] = detail

    enriched: list[dict[str, Any]] = []
    for item in results:
        detail = detail_map.get(item.get("mst", ""), {})
        enriched.append({**item, **detail})
    return enriched


def _normalize_public_query(value: str) -> str:
    cleaned = strip_exact_phrase_quotes(value)
    cleaned = (
        cleaned.replace("(", " ")
        .replace(")", " ")
        .replace(",", " ")
        .replace("?", " ")
        .replace("/", " ")
    )
    return " ".join(cleaned.split())


def _rewrite_public_query_variants(query: str) -> list[str]:
    variants = [query]
    for source, replacements in PUBLIC_QUERY_REWRITE_MAP.items():
        if source not in query:
            continue
        for replacement in replacements:
            variants.append(query.replace(source, replacement))
    return variants


def _drop_token_queries(tokens: list[str]) -> list[str]:
    if len(tokens) < 3:
        return []

    queries: list[str] = []
    for index in range(len(tokens)):
        candidate_tokens = tokens[:index] + tokens[index + 1 :]
        if len(candidate_tokens) < 2:
            continue
        queries.append(" ".join(candidate_tokens))
    return queries


def _build_public_search_queries(question: str) -> list[str]:
    normalized = _normalize_public_query(question)
    if not normalized:
        return []

    candidates: list[str] = []
    seen: set[str] = set()

    def add_candidate(query: str) -> None:
        normalized_query = _normalize_public_query(query)
        if not normalized_query or normalized_query in seen:
            return
        seen.add(normalized_query)
        candidates.append(normalized_query)

    for variant in _rewrite_public_query_variants(normalized):
        add_candidate(variant)

    filtered_tokens = [
        token
        for token in normalized.split()
        if token not in PUBLIC_SOURCE_HINT_TOKENS and token not in PUBLIC_QUERY_NOISE_TOKENS
    ]
    core_query = " ".join(filtered_tokens).strip()
    if core_query and core_query != normalized:
        for variant in _rewrite_public_query_variants(core_query):
            add_candidate(variant)

    dropped_queries = _drop_token_queries(core_query.split())
    for candidate_query in dropped_queries:
        for variant in _rewrite_public_query_variants(candidate_query):
            add_candidate(variant)

    core_tokens = [token for token in core_query.split() if token and token not in PUBLIC_TAX_TERMS]
    detected_tax_terms = [term for term in PUBLIC_TAX_TERMS if term in normalized]

    expansion_bases: list[str] = []
    for base in [core_query or normalized, *dropped_queries, " ".join(core_tokens).strip()]:
        if base:
            expansion_bases.append(base)

    if not detected_tax_terms:
        for base in expansion_bases:
            for term in PUBLIC_TAX_TERMS:
                add_candidate(f"{base} {term}")
    else:
        for base in expansion_bases:
            for term in detected_tax_terms:
                if term not in base:
                    add_candidate(f"{base} {term}")

    return candidates


def _public_result_key(item: dict[str, Any]) -> tuple[str, str]:
    source_type = str(item.get("source_type") or "unknown")
    reference = str(
        item.get("id")
        or item.get("serial_no")
        or item.get("mst")
        or item.get("law_id")
        or item.get("case_no")
        or item.get("title")
        or ""
    )
    return source_type, reference


async def _search_public_batch(query: str, *, per_source_limit: int) -> list[dict[str, Any]]:
    precedents, statutes, tribunal = await asyncio.gather(
        search_precedents(query, per_source_limit),
        search_statutes(query, per_source_limit),
        search_tribunal(query, per_source_limit),
    )
    precedents = _filter_and_sort_precedents(await _enrich_precedents(precedents))
    statutes = await _enrich_statutes(statutes)
    return [*precedents, *statutes, *tribunal]


async def _search_public_results(question: str, *, limit: int = PUBLIC_SOURCE_LIMIT) -> list[dict[str, Any]]:
    try:
        merged_results: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        exact_phrases = extract_exact_phrases(question)
        target_limit = max(limit, PUBLIC_CONTEXT_LIMIT)
        per_source_limit = min(target_limit * 2 if exact_phrases else target_limit, 60)

        for query in _build_public_search_queries(question):
            batch = await _search_public_batch(query, per_source_limit=per_source_limit)
            batch = filter_results_by_exact_phrases(batch, exact_phrases, PUBLIC_EXACT_MATCH_FIELDS)
            if not batch:
                continue

            for item in batch:
                key = _public_result_key(item)
                if key in seen:
                    continue
                seen.add(key)
                merged_results.append(item)
                if len(merged_results) >= target_limit:
                    return merged_results

        return merged_results
    except Exception as exc:  # pragma: no cover - defensive fallback
        logger.exception("Public law search failed: %s", exc)
        return []


async def _call_claude(system_prompt: str, context: str, question: str) -> str:
    user_prompt = (
        "아래 컨텍스트만 근거로 질문에 답변하세요. 컨텍스트에 없는 내용은 추정하지 말고 '등록된 자료에서 찾지 못했습니다'라고 적어주세요.\n\n"
        f"[컨텍스트]\n{context}\n\n"
        f"[질문]\n{question.strip()}"
    )

    try:
        return await generate_text(system_prompt, user_prompt, max_tokens=LLM_MAX_TOKENS, temperature=0.2)
    except LLMClientError as exc:
        raise RAGError(str(exc)) from exc


def _build_search_only_answer(
    private_results: list[dict[str, Any]],
    public_results: list[dict[str, Any]],
    *,
    reason: str | None = None,
) -> str:
    law_lines: list[str] = []
    for index, item in enumerate(public_results, start=1):
        source_type = item.get("source_type")
        if source_type == "precedent":
            title = _build_precedent_title(item)
        elif source_type == "statute":
            title = _build_statute_title(item)
        else:
            title = _build_tribunal_title(item)

        summary = _build_public_source_summary(item)
        if not summary:
            continue

        law_lines.append(f"[공개자료{index}] {title}: {_truncate_text(summary, 220)}")
        if len(law_lines) >= 3:
            break

    if not law_lines:
        for index, item in enumerate(private_results[:3], start=1):
            law_lines.append(f"[비공개자료{index}] {item.get('title') or '제목 없음'}: {_truncate_text(item.get('content'), 220)}")

    practical_lines = [
        f"[비공개자료{index}] {item.get('title') or '제목 없음'}: {_truncate_text(item.get('practical'), 220)}"
        for index, item in enumerate(private_results, start=1)
        if item.get("practical")
    ][:2]

    case_lines = [
        f"[비공개자료{index}] {item.get('title') or '제목 없음'}: {_truncate_text(item.get('content'), 220)}"
        for index, item in enumerate(private_results, start=1)
        if item.get("category") in {"civil", "case"}
    ][:2]
    if not case_lines:
        case_lines = [
            f"[공개자료{index}] {_build_tribunal_title(item)}: {_truncate_text(item.get('case_no') or item.get('source'), 180)}"
            for index, item in enumerate(public_results, start=1)
            if item.get("source_type") == "tribunal"
        ][:2]

    summary_lines = [
        f"비공개자료 {len(private_results)}건, 공개자료 {len(public_results)}건을 참고했습니다.",
    ]
    if reason:
        summary_lines.append(f"모델 호출이 원활하지 않아 검색 결과 기반 요약으로 제공합니다. ({reason})")

    return (
        "📋 법률 내용\n"
        + ("\n".join(law_lines) if law_lines else "등록된 자료에서 찾지 못했습니다.")
        + "\n\n🖥️ 전산 처리 방법\n"
        + ("\n".join(practical_lines) if practical_lines else "등록된 자료에서 찾지 못했습니다.")
        + "\n\n🗣️ 유사 민원 처리 사례\n"
        + ("\n".join(case_lines) if case_lines else "등록된 자료에서 찾지 못했습니다.")
        + "\n\n📌 참조 출처 요약\n"
        + "\n".join(summary_lines)
        + "\n\n정확한 사실관계와 과세 적용은 관련 법령 원문과 최신 판례를 다시 확인하고, 필요시 담당 부서 또는 세무 전문가와 상담하시기 바랍니다."
    )


def _build_no_result_answer(include_public: bool) -> str:
    public_note = "공개자료 검색도 함께 수행했지만 관련 결과를 찾지 못했습니다." if include_public else "공개자료 검색은 제외되었습니다."
    return (
        "📋 법률 내용\n"
        "등록된 자료에서 찾지 못했습니다.\n\n"
        "🖥️ 전산 처리 방법\n"
        "등록된 자료에서 찾지 못했습니다.\n\n"
        "🗣️ 유사 민원 처리 사례\n"
        "등록된 자료에서 찾지 못했습니다.\n\n"
        "📌 참조 출처 요약\n"
        f"검색된 참고자료가 없습니다. {public_note}\n\n"
        "정확한 사실관계와 과세 적용은 관련 법령 원문과 최신 판례를 다시 확인하고, 필요시 담당 부서 또는 세무 전문가와 상담하시기 바랍니다."
    )


async def generate_answer(question: str, include_public: bool = True) -> ChatResponse:
    normalized_question = question.strip()
    if not normalized_question:
        raise RAGError("질문이 비어 있습니다.")

    private_task = asyncio.create_task(_search_private_results(normalized_question, limit=PRIVATE_SOURCE_LIMIT))
    public_task: asyncio.Task[list[dict[str, Any]]] | None = None
    if include_public:
        public_task = asyncio.create_task(_search_public_results(normalized_question, limit=PUBLIC_SOURCE_LIMIT))

    private_results = await private_task
    public_results = await public_task if public_task is not None else []

    exact_phrases = extract_exact_phrases(normalized_question)
    private_results = filter_results_by_exact_phrases(private_results, exact_phrases, PRIVATE_EXACT_MATCH_FIELDS)
    public_results = filter_results_by_exact_phrases(public_results, exact_phrases, PUBLIC_EXACT_MATCH_FIELDS)

    context_private_results = private_results[:PRIVATE_CONTEXT_LIMIT]
    context_public_results = public_results[:PUBLIC_CONTEXT_LIMIT]
    context = _build_context(context_private_results, context_public_results)
    sources = _build_sources(private_results, public_results)

    if not private_results and not public_results:
        return ChatResponse(answer=_build_no_result_answer(include_public), sources=[])

    try:
        answer = await _call_claude(SYSTEM_PROMPT, context, normalized_question)
    except RAGError as exc:
        logger.warning("LLM answer generation unavailable. Returning search-only fallback: %s", exc)
        answer = _build_search_only_answer(context_private_results, context_public_results, reason=str(exc))
    return ChatResponse(answer=answer, sources=sources)


__all__ = [
    "generate_answer",
    "_build_context",
    "_call_claude",
    "SYSTEM_PROMPT",
    "RAGError",
]
