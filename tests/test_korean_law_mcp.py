from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import korean_law_mcp


def test_parse_tool_records_maps_metadata_to_public_result() -> None:
    text = """
행정규칙 검색 결과 (총 1건):

1. 지방세 운영기준
   - 행정규칙일련번호: 12345
   - 소관부처: 행정안전부
   - 공포일: 20240101
   - 링크: https://example.test/rule/12345
""".strip()

    records = korean_law_mcp._parse_tool_records(
        text,
        source_type="admin_rule",
        source_tool="search_admin_rule",
    )

    assert len(records) == 1
    assert records[0]["source_type"] == "admin_rule"
    assert records[0]["source_label"] == "행정규칙"
    assert records[0]["id"] == "12345"
    assert records[0]["title"] == "지방세 운영기준"
    assert records[0]["source"] == "행정안전부"
    assert records[0]["decision_date"] == "20240101"
    assert records[0]["detail_link"] == "https://example.test/rule/12345"


def test_parse_tool_records_maps_bracket_id_results() -> None:
    text = """
자치법규 검색 결과 (총 1건):

[SEOUL-1] 서울특별시 시세 조례
  지자체: 서울특별시
  시행일: 20250101
  링크: https://example.test/ordinance/SEOUL-1
""".strip()

    records = korean_law_mcp._parse_tool_records(
        text,
        source_type="ordinance",
        source_tool="search_ordinance",
    )

    assert records[0]["id"] == "SEOUL-1"
    assert records[0]["case_no"] == "SEOUL-1"
    assert records[0]["title"] == "서울특별시 시세 조례"
    assert records[0]["source"] == "서울특별시"


@pytest.mark.anyio
async def test_search_extended_public_combines_optional_mcp_sources(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_call_mcp_tool(tool_name: str, arguments: dict[str, object]) -> korean_law_mcp.McpToolResponse:
        if tool_name == "search_admin_rule":
            return korean_law_mcp.McpToolResponse(
                """
1. 지방세 운영기준
   - 행정규칙일련번호: 12345
   - 소관부처: 행정안전부
""".strip()
            )
        if tool_name == "search_decisions" and arguments.get("domain") == "interpretation":
            return korean_law_mcp.McpToolResponse(
                """
[INTERP-1] 취득세 감면 해석례
  회신기관: 법제처
  회신일: 20240202
""".strip()
            )
        return korean_law_mcp.McpToolResponse("검색 결과가 없습니다.")

    monkeypatch.setattr(korean_law_mcp, "get_law_oc", lambda: "law-oc-value")
    monkeypatch.setattr(korean_law_mcp, "call_mcp_tool", fake_call_mcp_tool)
    monkeypatch.setenv(korean_law_mcp.MCP_DOMAINS_ENV, "interpretation")

    results = await korean_law_mcp.search_extended_public("취득세", max_results=3)

    assert [item["source_type"] for item in results] == ["admin_rule", "interpretation"]
    assert results[0]["title"] == "지방세 운영기준"
    assert results[1]["source"] == "법제처"
