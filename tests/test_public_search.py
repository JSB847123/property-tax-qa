from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import rag
from app.routers import chat as chat_router


def test_build_public_search_queries_adds_tax_expansions() -> None:
    queries = rag._build_public_search_queries('부담부증여 관련 판례')

    assert queries[0] == '부담부증여 관련 판례'
    assert '부담부증여' in queries
    assert '부담부증여 취득세' in queries
    assert '부담부증여 재산세' in queries
    assert '부담부증여 등록면허세' in queries


def test_build_public_search_queries_simplifies_explicit_tax_queries() -> None:
    queries = rag._build_public_search_queries('부담부증여 취득세 판례')

    assert queries == ['부담부증여 취득세 판례', '부담부증여 취득세']


def test_build_public_search_queries_strips_quote_markers() -> None:
    queries = rag._build_public_search_queries('"부담부증여" 관련 판례')

    assert queries[0] == '부담부증여 관련 판례'
    assert '부담부증여' in queries


@pytest.mark.anyio
async def test_search_public_results_uses_tax_expansion_when_original_query_is_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, str]] = []

    async def fake_search_precedents(query: str, max_results: int) -> list[dict[str, str]]:
        calls.append(('precedent', query))
        return []

    async def fake_search_statutes(query: str, max_results: int) -> list[dict[str, str]]:
        calls.append(('statute', query))
        return []

    async def fake_search_tribunal(query: str, max_results: int) -> list[dict[str, str]]:
        calls.append(('tribunal', query))
        if query == '부담부증여 취득세':
            return [
                {
                    'source_type': 'tribunal',
                    'id': '90604',
                    'title': '부담부증여 부동산의 취득세 부과의 당부',
                    'case_no': '조심2010지0929',
                    'decision_date': '20110121',
                    'agency': '조세심판원',
                }
            ]
        return []

    monkeypatch.setattr(rag, 'search_precedents', fake_search_precedents)
    monkeypatch.setattr(rag, 'search_statutes', fake_search_statutes)
    monkeypatch.setattr(rag, 'search_tribunal', fake_search_tribunal)

    results = await rag._search_public_results('부담부증여 관련 판례')

    assert results
    assert results[0]['id'] == '90604'
    tribunal_queries = [query for source, query in calls if source == 'tribunal']
    assert tribunal_queries[:2] == ['부담부증여 관련 판례', '부담부증여']
    assert '부담부증여 취득세' in tribunal_queries


@pytest.mark.anyio
async def test_generate_answer_falls_back_to_search_only_summary_when_claude_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_private_results(question: str, *, limit: int = rag.PRIVATE_SOURCE_LIMIT) -> list[dict[str, object]]:
        return []

    async def fake_public_results(question: str, *, limit: int = rag.PUBLIC_SOURCE_LIMIT) -> list[dict[str, object]]:
        return [
            {
                'source_type': 'tribunal',
                'id': '90604',
                'title': '부담부증여 부동산의 취득세 부과의 당부',
                'case_no': '조심2010지0929',
                'decision_date': '20110121',
                'agency': '조세심판원',
                'source': '조세심판원 2011.01.21',
            }
        ]

    async def fake_call_claude(system_prompt: str, context: str, question: str) -> str:
        raise rag.RAGError('Claude API 호출에 실패했습니다.')

    monkeypatch.setattr(rag, '_search_private_results', fake_private_results)
    monkeypatch.setattr(rag, '_search_public_results', fake_public_results)
    monkeypatch.setattr(rag, '_call_claude', fake_call_claude)

    response = await rag.generate_answer('부담부증여 관련 판례', include_public=True)

    assert response.sources
    assert response.sources[0]['source_type'] == 'tribunal'
    assert '부담부증여 부동산의 취득세 부과의 당부' in response.answer
    assert '모델 호출이 원활하지 않아 검색 결과 기반 요약으로 제공합니다.' in response.answer


@pytest.mark.anyio
async def test_search_public_results_filters_low_information_precedents(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_search_precedents(query: str, max_results: int) -> list[dict[str, str]]:
        return [
            {
                'source_type': 'precedent',
                'id': '606047',
                'serial_no': '606047',
                'title': '판례',
                'detail_link': 'https://www.law.go.kr/DRF/lawService.do?target=prec&ID=606047&type=HTML',
            },
            {
                'source_type': 'precedent',
                'id': '231453',
                'serial_no': '231453',
                'title': '판례',
                'detail_link': 'https://www.law.go.kr/DRF/lawService.do?target=prec&ID=231453&type=HTML',
            },
        ]

    async def fake_search_statutes(query: str, max_results: int) -> list[dict[str, str]]:
        return []

    async def fake_search_tribunal(query: str, max_results: int) -> list[dict[str, str]]:
        return []

    async def fake_get_precedent_detail(serial_no: str) -> dict[str, str]:
        if serial_no == '231453':
            return {
                'source_type': 'precedent',
                'serial_no': '231453',
                'case_no': '2021다299976, 299983',
                'court_name': '대법원',
                'decision_date': '20220929',
                'summary': '부담부증여에도 증여 일반 조항이 적용된다는 점을 정리한 판결이다.',
            }
        return {'source_type': 'precedent', 'serial_no': serial_no}

    monkeypatch.setattr(rag, 'search_precedents', fake_search_precedents)
    monkeypatch.setattr(rag, 'search_statutes', fake_search_statutes)
    monkeypatch.setattr(rag, 'search_tribunal', fake_search_tribunal)
    monkeypatch.setattr(rag, 'get_precedent_detail', fake_get_precedent_detail)

    results = await rag._search_public_results('부담부증여 관련 판례')

    assert len(results) == 1
    assert results[0]['serial_no'] == '231453'
    assert results[0]['case_no'] == '2021다299976, 299983'


def test_normalize_source_item_keeps_public_summary_and_link() -> None:
    normalized = chat_router._normalize_source_item(
        {
            'citation': '[공개자료1]',
            'title': '대법원 2021다299976, 299983',
            'source': '대법원 2022.09.29.',
            'source_type': 'precedent',
            'reference': '2021다299976, 299983',
            'detail_link': 'https://www.law.go.kr/DRF/lawService.do?target=prec&ID=231453&type=HTML',
            'summary': '부담부증여에도 증여 일반 조항이 적용된다는 점을 정리한 판결이다.',
            'visibility': 'public',
        }
    )

    assert normalized['summary'] == '부담부증여에도 증여 일반 조항이 적용된다는 점을 정리한 판결이다.'
    assert normalized['detail_link'].startswith('https://www.law.go.kr/DRF/lawService.do')


@pytest.mark.anyio
async def test_search_public_results_respects_exact_phrase_filters(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_search_precedents(query: str, max_results: int) -> list[dict[str, str]]:
        return [
            {
                'source_type': 'precedent',
                'id': '231453',
                'serial_no': '231453',
                'title': '판례',
                'detail_link': 'https://www.law.go.kr/DRF/lawService.do?target=prec&ID=231453&type=HTML',
            },
            {
                'source_type': 'precedent',
                'id': '344984',
                'serial_no': '344984',
                'title': '판례',
                'detail_link': 'https://www.law.go.kr/DRF/lawService.do?target=prec&ID=344984&type=HTML',
            },
        ]

    async def fake_search_statutes(query: str, max_results: int) -> list[dict[str, str]]:
        return []

    async def fake_search_tribunal(query: str, max_results: int) -> list[dict[str, str]]:
        return []

    async def fake_get_precedent_detail(serial_no: str) -> dict[str, str]:
        if serial_no == '231453':
            return {
                'source_type': 'precedent',
                'serial_no': '231453',
                'case_no': '2021다299976, 299983',
                'court_name': '대법원',
                'decision_date': '20220929',
                'summary': '부담부증여에도 증여 일반 조항이 적용된다는 점을 정리한 판결이다.',
            }
        return {
            'source_type': 'precedent',
            'serial_no': '344984',
            'case_no': '수원지방법원-2020-구합-672',
            'court_name': '수원지방법원',
            'decision_date': '20210610',
            'summary': '취득세 일반 쟁점에 관한 판결이다.',
        }

    monkeypatch.setattr(rag, 'search_precedents', fake_search_precedents)
    monkeypatch.setattr(rag, 'search_statutes', fake_search_statutes)
    monkeypatch.setattr(rag, 'search_tribunal', fake_search_tribunal)
    monkeypatch.setattr(rag, 'get_precedent_detail', fake_get_precedent_detail)

    results = await rag._search_public_results('"부담부증여" 관련 판례')

    assert len(results) == 1
    assert results[0]['serial_no'] == '231453'
    assert '부담부증여' in results[0]['summary']


def test_build_precedent_title_prefers_meaningful_case_name() -> None:
    title = rag._build_precedent_title(
        {
            'title': '토지인도·소유권이전등기[부담부증여계약 사건]',
            'case_no': '2021다299976, 299983',
            'court_name': '대법원',
        }
    )

    assert title == '토지인도·소유권이전등기[부담부증여계약 사건]'


@pytest.mark.anyio
async def test_generate_answer_returns_all_sources_for_load_more(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_private_results(question: str, *, limit: int = rag.PRIVATE_SOURCE_LIMIT) -> list[dict[str, object]]:
        return []

    async def fake_public_results(question: str, *, limit: int = rag.PUBLIC_SOURCE_LIMIT) -> list[dict[str, object]]:
        return [
            {
                'source_type': 'tribunal',
                'id': f'case-{index}',
                'title': f'조세심판례 {index}',
                'case_no': f'조심{index:04d}',
                'decision_date': '20240101',
                'agency': '조세심판원',
            }
            for index in range(8)
        ]

    async def fake_call_claude(system_prompt: str, context: str, question: str) -> str:
        return '테스트 답변'

    monkeypatch.setattr(rag, '_search_private_results', fake_private_results)
    monkeypatch.setattr(rag, '_search_public_results', fake_public_results)
    monkeypatch.setattr(rag, '_call_claude', fake_call_claude)

    response = await rag.generate_answer('부담부증여 취득세 심판례', include_public=True)

    assert response.answer == '테스트 답변'
    assert len(response.sources) == 8
    assert response.sources[-1]['title'] == '조세심판례 7'


@pytest.mark.anyio
async def test_search_public_results_uses_special_relationship_rewrites(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, str]] = []

    async def fake_search_precedents(query: str, max_results: int) -> list[dict[str, str]]:
        calls.append(('precedent', query))
        return []

    async def fake_search_statutes(query: str, max_results: int) -> list[dict[str, str]]:
        calls.append(('statute', query))
        return []

    async def fake_search_tribunal(query: str, max_results: int) -> list[dict[str, str]]:
        calls.append(('tribunal', query))
        if query == '특수관계인 부동산 취득세':
            return [
                {
                    'source_type': 'tribunal',
                    'id': 'tax-1',
                    'title': '쟁점부동산의 취득을 특수관계인과의 거래로 보아 시가표준액을 과세표준으로 하여 취득세를 부과한 처분의 적법 여부',
                    'case_no': '조심2020지1234',
                    'decision_date': '20210121',
                    'agency': '조세심판원',
                }
            ]
        return []

    monkeypatch.setattr(rag, 'search_precedents', fake_search_precedents)
    monkeypatch.setattr(rag, 'search_statutes', fake_search_statutes)
    monkeypatch.setattr(rag, 'search_tribunal', fake_search_tribunal)

    results = await rag._search_public_results('특수관계인간 부동산 취득세 관련 판례')

    assert results
    assert results[0]['id'] == 'tax-1'
    tribunal_queries = [query for source, query in calls if source == 'tribunal']
    assert '특수관계인 부동산 취득세' in tribunal_queries
