from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import law_search


def test_normalize_detail_link_promotes_relative_urls_to_absolute_law_host() -> None:
    relative = '/DRF/lawService.do?target=prec&ID=231453&type=HTML'

    assert law_search._normalize_detail_link(relative) == 'https://www.law.go.kr/DRF/lawService.do?target=prec&ID=231453&type=HTML'
    assert law_search._normalize_detail_link('https://www.law.go.kr/DRF/lawService.do?target=prec&ID=231453&type=HTML') == 'https://www.law.go.kr/DRF/lawService.do?target=prec&ID=231453&type=HTML'
