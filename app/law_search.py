from __future__ import annotations

import asyncio
import logging
from typing import Any, Iterable
from urllib.parse import parse_qs, urljoin, urlparse
from xml.etree import ElementTree as ET

import httpx

from app.runtime_settings import get_law_oc


logger = logging.getLogger(__name__)

LAW_BASE_URL = "https://www.law.go.kr"
LAW_SEARCH_URL = "http://www.law.go.kr/DRF/lawSearch.do"
LAW_SERVICE_URL = "http://www.law.go.kr/DRF/lawService.do"
REQUEST_TIMEOUT = 10.0
MAX_RESULTS_LIMIT = 100
TRIBUNAL_PRIMARY_TARGET = "ttSpecialDecc"
TRIBUNAL_FALLBACK_TARGET = "expc"



def _normalize_max_results(max_results: int) -> int:
    return max(1, min(int(max_results or 5), MAX_RESULTS_LIMIT))


def _strip_namespace(tag: str) -> str:
    return tag.split("}", 1)[-1] if "}" in tag else tag


def _clean_text(value: str | None) -> str:
    if not value:
        return ""
    return " ".join(value.split())


def _node_text(node: ET.Element | None) -> str:
    if node is None:
        return ""
    return _clean_text("".join(node.itertext()))


def _child_tags(node: ET.Element) -> set[str]:
    return {_strip_namespace(child.tag) for child in list(node)}


def _has_record_signature(node: ET.Element, tags: Iterable[str]) -> bool:
    child_tag_set = _child_tags(node)
    return any(tag in child_tag_set for tag in tags)


def _find_record_nodes(root: ET.Element, signature_tags: Iterable[str]) -> list[ET.Element]:
    signature_list = list(signature_tags)
    direct_matches = [child for child in list(root) if _has_record_signature(child, signature_list)]
    if direct_matches:
        return direct_matches

    matches: list[ET.Element] = []
    seen: set[int] = set()
    for node in root.iter():
        if node is root:
            continue
        if _has_record_signature(node, signature_list):
            node_id = id(node)
            if node_id not in seen:
                matches.append(node)
                seen.add(node_id)
    return matches


def _find_text(node: ET.Element, candidates: Iterable[str], *, recursive: bool = True) -> str:
    if recursive:
        elements = node.iter()
    else:
        elements = list(node)

    for candidate in candidates:
        for element in elements:
            if _strip_namespace(element.tag) == candidate:
                value = _node_text(element)
                if value:
                    return value
        if recursive:
            elements = node.iter()
    return ""


def _extract_query_param(url: str, name: str) -> str:
    if not url:
        return ""
    try:
        return parse_qs(urlparse(url).query).get(name, [""])[0]
    except Exception:
        return ""


def _normalize_detail_link(url: str | None) -> str:
    link = (url or "").strip()
    if not link:
        return ""
    if link.startswith(("http://", "https://")):
        return link
    if link.startswith("/"):
        return urljoin(LAW_BASE_URL, link)
    return urljoin(f"{LAW_BASE_URL}/", link)


async def _request_xml(
    url: str,
    params: dict[str, Any],
    client: httpx.AsyncClient | None = None,
) -> ET.Element | None:
    if client is not None:
        return await _perform_request(client, url, params)

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT, follow_redirects=True) as async_client:
        return await _perform_request(async_client, url, params)


async def _perform_request(
    client: httpx.AsyncClient,
    url: str,
    params: dict[str, Any],
) -> ET.Element | None:
    try:
        response = await client.get(url, params=params)
        response.raise_for_status()
        return ET.fromstring(response.text)
    except (httpx.HTTPError, ET.ParseError, ValueError) as exc:
        logger.warning("Law API request failed for %s with params=%s: %s", url, params, exc)
        return None


def _base_params(target: str) -> dict[str, Any] | None:
    law_oc = get_law_oc()
    if not law_oc:
        logger.warning("LAW_OC is not configured in .env")
        return None
    return {"OC": law_oc, "target": target, "type": "XML"}


def _map_precedent_record(node: ET.Element) -> dict[str, Any]:
    serial_no = _find_text(node, ["판례일련번호", "판례정보일련번호"], recursive=False) or _find_text(node, ["판례일련번호", "판례정보일련번호"])
    title = _find_text(node, ["사건명"], recursive=False) or _find_text(node, ["사건명"])
    case_no = _find_text(node, ["사건번호"], recursive=False) or _find_text(node, ["사건번호"])
    decision_date = _find_text(node, ["선고일자"], recursive=False) or _find_text(node, ["선고일자"])
    court_name = _find_text(node, ["법원명"], recursive=False) or _find_text(node, ["법원명"])
    detail_link = _normalize_detail_link(
        _find_text(node, ["판례상세링크"], recursive=False) or _find_text(node, ["판례상세링크"])
    )

    return {
        "source_type": "precedent",
        "id": serial_no or case_no,
        "serial_no": serial_no,
        "title": title,
        "case_name": title,
        "case_no": case_no,
        "decision_date": decision_date,
        "court_name": court_name,
        "detail_link": detail_link,
    }


def _map_statute_record(node: ET.Element) -> dict[str, Any]:
    detail_link = _normalize_detail_link(
        _find_text(node, ["법령상세링크"], recursive=False) or _find_text(node, ["법령상세링크"])
    )
    mst = (
        _find_text(node, ["법령일련번호", "MST"], recursive=False)
        or _find_text(node, ["법령일련번호", "MST"])
        or _extract_query_param(detail_link, "MST")
    )
    law_id = (
        _find_text(node, ["법령ID"], recursive=False)
        or _find_text(node, ["법령ID"])
        or _extract_query_param(detail_link, "ID")
    )
    title = _find_text(node, ["법령명한글", "법령명_한글"], recursive=False) or _find_text(node, ["법령명한글", "법령명_한글"])

    return {
        "source_type": "statute",
        "id": mst or law_id or title,
        "mst": mst,
        "law_id": law_id,
        "title": title,
        "name_kr": title,
        "short_name": _find_text(node, ["법령약칭명", "법령명약칭"], recursive=False) or _find_text(node, ["법령약칭명", "법령명약칭"]),
        "promulgation_date": _find_text(node, ["공포일자"], recursive=False) or _find_text(node, ["공포일자"]),
        "promulgation_no": _find_text(node, ["공포번호"], recursive=False) or _find_text(node, ["공포번호"]),
        "effective_date": _find_text(node, ["시행일자"], recursive=False) or _find_text(node, ["시행일자"]),
        "ministry": _find_text(node, ["소관부처명", "소관부처"], recursive=False) or _find_text(node, ["소관부처명", "소관부처"]),
        "detail_link": detail_link,
    }


def _map_tribunal_record(node: ET.Element, *, source_target: str) -> dict[str, Any]:
    if source_target == TRIBUNAL_PRIMARY_TARGET:
        serial_no = _find_text(node, ["특별행정심판재결례일련번호"], recursive=False) or _find_text(node, ["특별행정심판재결례일련번호"])
        title = _find_text(node, ["사건명"], recursive=False) or _find_text(node, ["사건명"])
        case_no = _find_text(node, ["청구번호"], recursive=False) or _find_text(node, ["청구번호"])
        return {
            "source_type": "tribunal",
            "record_type": TRIBUNAL_PRIMARY_TARGET,
            "id": serial_no or case_no or title,
            "serial_no": serial_no,
            "title": title,
            "case_name": title,
            "case_no": case_no,
            "decision_date": _find_text(node, ["의결일자"], recursive=False) or _find_text(node, ["의결일자"]),
            "disposition_date": _find_text(node, ["처분일자"], recursive=False) or _find_text(node, ["처분일자"]),
            "agency": _find_text(node, ["처분청"], recursive=False) or _find_text(node, ["처분청"]),
            "tribunal_name": _find_text(node, ["재결청"], recursive=False) or _find_text(node, ["재결청"]),
            "decision_type": _find_text(node, ["재결구분명"], recursive=False) or _find_text(node, ["재결구분명"]),
            "detail_link": _normalize_detail_link(
                _find_text(node, ["행정심판재결례상세링크"], recursive=False)
                or _find_text(node, ["행정심판재결례상세링크"])
            ),
        }

    serial_no = _find_text(node, ["법령해석례일련번호"], recursive=False) or _find_text(node, ["법령해석례일련번호"])
    title = _find_text(node, ["안건명"], recursive=False) or _find_text(node, ["안건명"])
    case_no = _find_text(node, ["안건번호"], recursive=False) or _find_text(node, ["안건번호"])
    return {
        "source_type": "tribunal",
        "record_type": TRIBUNAL_FALLBACK_TARGET,
        "id": serial_no or case_no or title,
        "serial_no": serial_no,
        "title": title,
        "case_name": title,
        "case_no": case_no,
        "decision_date": _find_text(node, ["회신일자"], recursive=False) or _find_text(node, ["회신일자"]),
        "agency": _find_text(node, ["회신기관명"], recursive=False) or _find_text(node, ["회신기관명"]),
        "querying_agency": _find_text(node, ["질의기관명"], recursive=False) or _find_text(node, ["질의기관명"]),
        "detail_link": _normalize_detail_link(
            _find_text(node, ["법령해석례상세링크"], recursive=False)
            or _find_text(node, ["법령해석례상세링크"])
        ),
    }


def _parse_articles(root: ET.Element) -> list[dict[str, Any]]:
    article_nodes = _find_record_nodes(root, ["조문번호", "조문제목", "조문내용"])
    articles: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()

    for node in article_nodes:
        article_no = _find_text(node, ["조문번호"], recursive=False) or _find_text(node, ["조문번호"])
        article_branch = _find_text(node, ["조문가지번호"], recursive=False) or _find_text(node, ["조문가지번호"])
        article_title = _find_text(node, ["조문제목"], recursive=False) or _find_text(node, ["조문제목"])
        article_content = _find_text(node, ["조문내용"], recursive=False) or _find_text(node, ["조문내용"])
        reference = _find_text(node, ["조문참고자료"], recursive=False) or _find_text(node, ["조문참고자료"])

        if not any([article_no, article_title, article_content]):
            continue

        dedupe_key = (article_no, article_branch, article_content)
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)

        articles.append(
            {
                "article_no": article_no,
                "article_branch_no": article_branch,
                "article_title": article_title,
                "article_content": article_content,
                "reference": reference,
            }
        )

    return articles


async def search_precedents(
    query: str,
    max_results: int = 5,
    *,
    client: httpx.AsyncClient | None = None,
) -> list[dict[str, Any]]:
    if not query or not query.strip():
        return []

    params = _base_params("prec")
    if params is None:
        return []

    params.update({"query": query.strip(), "display": _normalize_max_results(max_results)})
    root = await _request_xml(LAW_SEARCH_URL, params, client=client)
    if root is None:
        return []

    records: list[dict[str, Any]] = []
    for node in _find_record_nodes(root, ["판례일련번호", "판례정보일련번호", "사건명", "사건번호"]):
        record = _map_precedent_record(node)
        if record["title"] or record["serial_no"]:
            records.append(record)
    return records[: _normalize_max_results(max_results)]


async def get_precedent_detail(
    serial_no: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    if not serial_no or not serial_no.strip():
        return {}

    params = _base_params("prec")
    if params is None:
        return {}

    params.update({"ID": serial_no.strip()})
    root = await _request_xml(LAW_SERVICE_URL, params, client=client)
    if root is None:
        return {}

    return {
        "source_type": "precedent",
        "serial_no": _find_text(root, ["판례정보일련번호", "판례일련번호"]) or serial_no.strip(),
        "title": _find_text(root, ["사건명"]),
        "case_name": _find_text(root, ["사건명"]),
        "case_no": _find_text(root, ["사건번호"]),
        "decision_date": _find_text(root, ["선고일자"]),
        "court_name": _find_text(root, ["법원명"]),
        "decision_type": _find_text(root, ["판결유형"]),
        "holding": _find_text(root, ["판시사항"]),
        "summary": _find_text(root, ["판결요지"]),
        "references": _find_text(root, ["참조조문"]),
        "related_precedents": _find_text(root, ["참조판례"]),
        "full_text": _find_text(root, ["판례내용"]),
    }


async def search_statutes(
    query: str,
    max_results: int = 5,
    *,
    client: httpx.AsyncClient | None = None,
) -> list[dict[str, Any]]:
    if not query or not query.strip():
        return []

    params = _base_params("law")
    if params is None:
        return []

    params.update({"query": query.strip(), "display": _normalize_max_results(max_results)})
    root = await _request_xml(LAW_SEARCH_URL, params, client=client)
    if root is None:
        return []

    records: list[dict[str, Any]] = []
    for node in _find_record_nodes(root, ["법령일련번호", "법령명한글", "법령명_한글", "법령ID"]):
        record = _map_statute_record(node)
        if record["title"] or record["mst"] or record["law_id"]:
            records.append(record)
    return records[: _normalize_max_results(max_results)]


async def get_statute_detail(
    mst: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    if not mst or not mst.strip():
        return {}

    params = _base_params("law")
    if params is None:
        return {}

    params.update({"MST": mst.strip()})
    root = await _request_xml(LAW_SERVICE_URL, params, client=client)
    if root is None:
        return {}

    articles = _parse_articles(root)
    return {
        "source_type": "statute",
        "mst": mst.strip(),
        "law_id": _find_text(root, ["법령ID"]),
        "title": _find_text(root, ["법령명_한글", "법령명한글"]),
        "name_kr": _find_text(root, ["법령명_한글", "법령명한글"]),
        "name_hanja": _find_text(root, ["법령명_한자"]),
        "short_name": _find_text(root, ["법령명약칭", "법령약칭명"]),
        "promulgation_date": _find_text(root, ["공포일자"]),
        "promulgation_no": _find_text(root, ["공포번호"]),
        "effective_date": _find_text(root, ["시행일자"]),
        "amendment_type": _find_text(root, ["제개정구분"]),
        "ministry": _find_text(root, ["소관부처", "소관부처명"]),
        "department": _find_text(root, ["부서명"]),
        "contact": _find_text(root, ["부서연락처", "전화번호"]),
        "articles": articles,
        "full_text": "\n\n".join(article["article_content"] for article in articles if article["article_content"]),
    }


async def _search_tribunal_target(
    query: str,
    max_results: int,
    target: str,
    client: httpx.AsyncClient | None = None,
) -> list[dict[str, Any]]:
    params = _base_params(target)
    if params is None:
        return []

    params.update({"query": query.strip(), "display": _normalize_max_results(max_results)})
    root = await _request_xml(LAW_SEARCH_URL, params, client=client)
    if root is None:
        return []

    if target == TRIBUNAL_PRIMARY_TARGET:
        signature = ["특별행정심판재결례일련번호", "사건명", "청구번호"]
    else:
        signature = ["법령해석례일련번호", "안건명", "안건번호"]

    records: list[dict[str, Any]] = []
    for node in _find_record_nodes(root, signature):
        record = _map_tribunal_record(node, source_target=target)
        if record["title"] or record["serial_no"]:
            records.append(record)
    return records[: _normalize_max_results(max_results)]


async def search_tribunal(
    query: str,
    max_results: int = 5,
    *,
    client: httpx.AsyncClient | None = None,
) -> list[dict[str, Any]]:
    if not query or not query.strip():
        return []

    primary_results = await _search_tribunal_target(
        query=query,
        max_results=max_results,
        target=TRIBUNAL_PRIMARY_TARGET,
        client=client,
    )
    if primary_results:
        return primary_results

    return await _search_tribunal_target(
        query=query,
        max_results=max_results,
        target=TRIBUNAL_FALLBACK_TARGET,
        client=client,
    )


async def search_all(query: str, max_results: int = 5) -> list[dict[str, Any]]:
    if not query or not query.strip():
        return []

    normalized_max_results = _normalize_max_results(max_results)
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT, follow_redirects=True) as client:
        precedents, statutes, tribunal = await asyncio.gather(
            search_precedents(query, normalized_max_results, client=client),
            search_statutes(query, normalized_max_results, client=client),
            search_tribunal(query, normalized_max_results, client=client),
        )

    return [*precedents, *statutes, *tribunal]


__all__ = [
    "search_precedents",
    "get_precedent_detail",
    "search_statutes",
    "get_statute_detail",
    "search_tribunal",
    "search_all",
    "get_law_oc",
    "_normalize_detail_link",
]
