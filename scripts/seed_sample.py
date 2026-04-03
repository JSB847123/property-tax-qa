from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.models import DocumentCreate
from app.private_store import StorageError, add_document, get_all_documents


SAMPLE_DOCUMENTS = [
    DocumentCreate(
        category="civil",
        is_private=True,
        title="증여취득 신고 누락 민원",
        source="민원처리 내부기록",
        content="증여로 취득한 부동산에 대해 취득세 신고가 누락된 사례로, 사실관계와 등기일자를 확인하여 무신고 사유를 검토하고 자진신고 안내 및 보완 접수를 진행하였다.",
        practical="위택스 신고자료 조회 후 과세자료를 대조하고, 취득일자를 기준으로 신고납부서 재작성 및 가산세 적용 여부를 검토한 뒤 보완 접수한다.",
        date="2026-03-10",
        tags=["취득세", "증여", "무신고", "민원"],
    ),
    DocumentCreate(
        category="civil",
        is_private=True,
        title="다주택자 중과세 이의 민원",
        source="민원처리 내부기록",
        content="다주택자가 조정대상지역 주택 취득 후 중과세 적용에 대해 이의를 제기한 사례로, 기존 주택 수 산정과 일시적 2주택 예외 여부를 검토하여 과세 적정성을 설명하였다.",
        practical="지방세 시스템에서 주택 수 조회 자료와 취득물건 정보를 확인하고, 중과세율 적용 사유를 민원회신서에 기재한 후 필요 시 경정 가능 여부를 별도 검토한다.",
        date="2026-03-14",
        tags=["취득세", "중과세", "다주택", "이의신청"],
    ),
    DocumentCreate(
        category="theory",
        is_private=True,
        title="사실상 취득의 판단 기준 정리",
        source="내부 검토 메모",
        content="사실상 취득은 형식적 등기 여부와 별개로 대금 지급, 사용수익, 처분권 이전, 잔금 정산, 점유 이전 등 실질적 지배 이전 여부를 종합하여 판단한다. 계약 형식보다 실질 귀속과 경제적 이익 이전 시점을 중점적으로 본다.",
        practical=None,
        date="2026-02-28",
        tags=["취득세", "사실상취득", "판단기준"],
    ),
    DocumentCreate(
        category="case",
        is_private=True,
        title="농지 취득세 감면 질의회신",
        source="질의회신 참고사례",
        content="자경 목적 농지 취득에 대한 감면 적용 여부를 질의한 사례로, 농업인 요건과 직접 경작 계획, 취득 후 이용 실태를 중심으로 감면 가능 여부를 검토하였다.",
        practical=None,
        date="2026-01-22",
        tags=["취득세", "감면", "농지", "질의회신"],
    ),
    DocumentCreate(
        category="theory",
        is_private=True,
        title="재산세 과세표준 산정 실무 정리",
        source="내부 실무 정리",
        content="재산세 과세표준은 공시가격 또는 시가표준액을 기초로 하여 공정시장가액비율을 적용하고, 과세기준일 현재의 소유 및 현황을 반영해 산정한다. 건축물과 토지의 과세대상 구분 및 비과세·감면 여부를 함께 확인해야 한다.",
        practical="세정시스템에서 과세대장과 공시가격 자료를 연계 조회하고, 공정시장가액비율 반영값을 확인한 뒤 감면코드 적용 여부와 세액 재계산 결과를 검증한다.",
        date="2026-03-03",
        tags=["재산세", "과세표준", "공시가격", "실무"],
    ),
]


def main() -> int:
    existing = get_all_documents(page=1, page_size=500)
    existing_titles = {item["title"] for item in existing.get("items", [])}

    created_count = 0
    skipped_count = 0

    for document in SAMPLE_DOCUMENTS:
        if document.title in existing_titles:
            skipped_count += 1
            print(f"[SKIP] {document.title}")
            continue

        try:
            stored = add_document(document)
        except StorageError as exc:
            print(f"[ERROR] {document.title}: {exc}")
            return 1

        created_count += 1
        existing_titles.add(document.title)
        print(f"[OK] {stored.title} ({stored.id})")

    print(f"완료: 생성 {created_count}건, 건너뜀 {skipped_count}건")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
