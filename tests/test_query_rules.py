from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import query_rules


def test_extract_exact_phrases_reads_double_quotes() -> None:
    assert query_rules.extract_exact_phrases('"부담부증여" 취득세 판례') == ['부담부증여']


def test_filter_results_by_exact_phrases_keeps_only_matching_items() -> None:
    results = [
        {'title': '대법원 2021다299976, 299983', 'summary': '부담부증여에도 증여 일반 조항이 적용된다는 점을 정리한 판결이다.'},
        {'title': '수원지방법원-2020-구합-672', 'summary': '취득세 일반 쟁점에 관한 판결이다.'},
    ]

    filtered = query_rules.filter_results_by_exact_phrases(results, ['부담부증여'], ('title', 'summary'))

    assert len(filtered) == 1
    assert filtered[0]['title'] == '대법원 2021다299976, 299983'
