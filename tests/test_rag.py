from __future__ import annotations

import csv
import io
import sys
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import database, private_store
from app.main import app
from app.models import DocumentCreate
from app.routers import documents as documents_router


class FakeCollection:
    def __init__(self) -> None:
        self._items: dict[str, dict[str, Any]] = {}

    def add(self, ids: list[str], documents: list[str], metadatas: list[dict[str, Any]]) -> None:
        for item_id, document, metadata in zip(ids, documents, metadatas, strict=False):
            self._items[item_id] = {"document": document, "metadata": metadata}

    def upsert(self, ids: list[str], documents: list[str], metadatas: list[dict[str, Any]]) -> None:
        self.add(ids, documents, metadatas)

    def delete(self, ids: list[str]) -> None:
        for item_id in ids:
            self._items.pop(item_id, None)

    def count(self) -> int:
        return len(self._items)

    def query(
        self,
        query_texts: list[str],
        n_results: int,
        where: dict[str, Any] | None = None,
        include: list[str] | None = None,
    ) -> dict[str, list[list[Any]]]:
        query = (query_texts[0] or "").lower()
        matches: list[tuple[float, str]] = []

        for item_id, payload in self._items.items():
            metadata = payload["metadata"]
            if where and any(metadata.get(key) != value for key, value in where.items()):
                continue

            document = payload["document"].lower()
            tokens = [token for token in query.split() if token]
            token_score = sum(document.count(token) for token in tokens)
            full_score = document.count(query) if query else 0
            score = full_score * 10 + token_score
            distance = 1 / (score + 1) if score > 0 else 9999.0
            matches.append((distance, item_id))

        matches.sort(key=lambda item: item[0])
        selected = matches[:n_results]
        return {
            "ids": [[item_id for _, item_id in selected]],
            "distances": [[distance for distance, _ in selected]],
            "documents": [[self._items[item_id]["document"] for _, item_id in selected]],
            "metadatas": [[self._items[item_id]["metadata"] for _, item_id in selected]],
        }


@pytest.fixture()
def isolated_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> FakeCollection:
    temp_db_path = tmp_path / "tax_rag_test.db"

    monkeypatch.setattr(database, "DATA_DIR", tmp_path)
    monkeypatch.setattr(database, "DATABASE_PATH", temp_db_path)
    monkeypatch.setattr(database, "DB_PATH", temp_db_path)
    monkeypatch.setattr(private_store, "CHROMA_PATH", tmp_path / "chroma")
    monkeypatch.setattr(private_store, "CHROMA_DIR", tmp_path / "chroma")
    monkeypatch.setattr(private_store, "_collection", None)
    monkeypatch.setattr(private_store, "_chroma_client", None)

    fake_collection = FakeCollection()
    monkeypatch.setattr(private_store, "get_collection", lambda: fake_collection)

    database.init_db()
    return fake_collection


@pytest.fixture()
def sqlite_only_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    temp_db_path = tmp_path / "tax_rag_test.db"

    monkeypatch.setattr(database, "DATA_DIR", tmp_path)
    monkeypatch.setattr(database, "DATABASE_PATH", temp_db_path)
    monkeypatch.setattr(database, "DB_PATH", temp_db_path)
    monkeypatch.setattr(private_store, "CHROMA_PATH", tmp_path / "chroma")
    monkeypatch.setattr(private_store, "CHROMA_DIR", tmp_path / "chroma")
    monkeypatch.setattr(private_store, "_collection", None)
    monkeypatch.setattr(private_store, "_chroma_client", None)

    def _raise_storage_error() -> Any:
        raise private_store.StorageError("chromadb is not installed. Install requirements.txt dependencies first.")

    monkeypatch.setattr(private_store, "get_collection", _raise_storage_error)
    database.init_db()


@pytest.fixture()
def client(isolated_store: FakeCollection) -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


def test_add_document(isolated_store: FakeCollection) -> None:
    document = DocumentCreate(
        category="civil",
        is_private=True,
        title="증여취득 신고 누락 민원",
        source="민원처리 내부기록",
        content="증여로 취득한 부동산의 신고 누락 여부를 검토한 민원 기록이다.",
        practical="위택스 신고자료를 확인하고 보완 접수를 진행한다.",
        date="2026-04-03",
        tags=["취득세", "증여"],
    )

    created = private_store.add_document(document)
    fetched = private_store.get_document_by_id(created.id)

    assert fetched is not None
    assert fetched.title == document.title
    assert fetched.category == "civil"
    assert fetched.tags == ["취득세", "증여"]


def test_search_private(isolated_store: FakeCollection) -> None:
    documents = [
        DocumentCreate(
            category="theory",
            is_private=True,
            title="사실상 취득의 판단 기준 정리",
            source="내부 검토 메모",
            content="사실상 취득은 대금 지급과 사용수익의 이전 등 실질을 기준으로 판단한다.",
            practical=None,
            date="2026-04-03",
            tags=["취득세", "사실상취득"],
        ),
        DocumentCreate(
            category="case",
            is_private=True,
            title="농지 취득세 감면 질의회신",
            source="질의회신 참고사례",
            content="농지 취득세 감면 적용 여부를 검토한 사례다.",
            practical=None,
            date="2026-04-02",
            tags=["감면", "농지"],
        ),
    ]

    for document in documents:
        private_store.add_document(document)

    results = private_store.search_similar("사실상 취득 판단", top_k=5)

    assert results
    assert results[0]["title"] == "사실상 취득의 판단 기준 정리"
    assert any(item["category"] == "theory" for item in results)


def test_search_private_falls_back_to_sqlite(sqlite_only_store: None) -> None:
    created = private_store.add_document(
        DocumentCreate(
            category="theory",
            is_private=True,
            title="사실상 취득의 판단 기준 정리",
            source="내부 검토 메모",
            content="사실상 취득은 대금 지급과 사용수익의 이전 등 실질을 기준으로 판단한다.",
            practical="잔금일과 점유 이전일을 함께 확인한다.",
            date="2026-04-03",
            tags=["취득세", "사실상취득"],
        )
    )

    fetched = private_store.get_document_by_id(created.id)
    results = private_store.search_similar("사실상 취득 판단", top_k=5)

    assert fetched is not None
    assert results
    assert results[0]["id"] == created.id
    assert results[0]["title"] == "사실상 취득의 판단 기준 정리"
    assert results[0]["distance"] is not None


def test_csv_upload() -> None:
    pytest.importorskip("multipart")

    csv_content = (
        "분류,제목,출처,내용,전산적용,날짜,태그\n"
        "민원처리,증여취득 신고 누락 민원,민원처리 내부기록,신고 누락 민원 처리 기록,위택스 보완 입력,2026-04-03,취득세;증여;민원\n"
    )
    reader = csv.DictReader(io.StringIO(csv_content))
    row = next(reader)

    document = documents_router._build_document_create_from_csv(row, 2)

    assert document.category == "civil"
    assert document.title == "증여취득 신고 누락 민원"
    assert document.practical == "위택스 보완 입력"
    assert document.tags == ["취득세", "증여", "민원"]

def test_csv_upload_accepts_other_category() -> None:
    pytest.importorskip("multipart")

    csv_content = (
        "분류,제목,출처,내용,전산적용,날짜,태그\n"
        "기타,기타 참고 메모,내부 참고,보조 설명 메모,,2026-04-03,참고;메모\n"
    )
    reader = csv.DictReader(io.StringIO(csv_content))
    row = next(reader)

    document = documents_router._build_document_create_from_csv(row, 2)

    assert document.category == "other"
    assert document.title == "기타 참고 메모"
    assert document.tags == ["참고", "메모"]


def test_parse_markdown_documents() -> None:
    markdown_content = """# 경매취득 정리
- 분류: 이론
- 출처: 내부 검토 메모
- 날짜: 2026-01-01
- 태그: 취득세;경매취득
## 내용(예시)
경매로 부동산을 취득하는 경우에는 사실상 취득가격으로써 그 경매가액이 그대로 과세표준이 된다.
## 전산적용(예시)
매각대금완납증명원 등 확인 후 취득가액 입력, 과세표준 확인

---
# 시가인정액 관련 문의
- 분류: 민원처리
- 출처: 민원처리 내부기록
- 날짜: 2026-01-02
- 태그: 취득세;증여;민원
내용(예시):
질문: 시가인정액이 없으면 시가표준액으로 적용하는지 문의
답변: (작성)
전산적용(예시):
확인 후 적용
"""

    rows = documents_router._parse_markdown_documents(markdown_content)
    first = documents_router._build_document_create_from_markdown(rows[0], 1)
    second = documents_router._build_document_create_from_markdown(rows[1], 2)

    assert len(rows) == 2
    assert first.category == "theory"
    assert first.title == "경매취득 정리"
    assert first.content == "경매로 부동산을 취득하는 경우에는 사실상 취득가격으로써 그 경매가액이 그대로 과세표준이 된다."
    assert first.practical == "매각대금완납증명원 등 확인 후 취득가액 입력, 과세표준 확인"
    assert first.tags == ["취득세", "경매취득"]
    assert second.category == "civil"
    assert second.title == "시가인정액 관련 문의"
    assert second.content == "질문: 시가인정액이 없으면 시가표준액으로 적용하는지 문의\n답변: (작성)"
    assert second.practical == "확인 후 적용"


def test_markdown_bulk_upload(client: TestClient) -> None:
    pytest.importorskip("multipart")

    markdown_content = """# 경매취득 정리
- 분류: 이론
- 출처: 내부 검토 메모
- 날짜: 2026-01-01
- 태그: 취득세;경매취득
## 내용(예시)
경매로 부동산을 취득하는 경우에는 사실상 취득가격으로써 그 경매가액이 그대로 과세표준이 된다.
## 전산적용(예시)
매각대금완납증명원 등 확인 후 취득가액 입력, 과세표준 확인

---
# 시가인정액 관련 문의
- 분류: 민원처리
- 출처: 민원처리 내부기록
- 날짜: 2026-01-02
- 태그: 취득세;증여;민원
## 내용(예시)
질문: 시가인정액이 없으면 시가표준액으로 적용하는지 문의
답변: (작성)
## 전산적용(예시)
확인 후 적용
"""

    response = client.post(
        "/api/documents/bulk",
        files={"file": ("bulk.md", markdown_content.encode("utf-8"), "text/markdown")},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["file_type"] == "markdown"
    assert payload["created_count"] == 2
    assert payload["failed_count"] == 0
    assert payload["documents"][0]["category"] == "theory"
    assert payload["documents"][1]["category"] == "civil"
