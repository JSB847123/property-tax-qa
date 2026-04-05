from __future__ import annotations

import csv
import io
import json
import logging
import re
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from pydantic import ValidationError

from app.database import TABLE_NAME, get_connection
from app.models import DocumentCreate, DocumentResponse, DocumentUpdate
from app.private_store import StorageError, add_document, delete_document, get_collection, get_document_by_id, update_document


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/documents", tags=["documents"])

KOREAN_TO_CATEGORY = {
    "판례": "precedent",
    "심판례": "tribunal",
    "사례": "case",
    "민원처리": "civil",
    "이론": "theory",
    "법령": "statute",
    "기타": "other",
}
CATEGORY_TO_KOREAN = {value: key for key, value in KOREAN_TO_CATEGORY.items()}
CSV_HEADERS = ["분류", "제목", "출처", "내용", "전산적용", "날짜", "태그"]
MARKDOWN_METADATA_KEYS = {"분류", "제목", "출처", "날짜", "태그"}
MARKDOWN_SECTION_KEYS = {"내용", "전산적용"}
SUPPORTED_MARKDOWN_EXTENSIONS = {".md", ".markdown"}


def _storage_http_exception(exc: Exception) -> HTTPException:
    message = str(exc)
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE if "not installed" in message.lower() else status.HTTP_500_INTERNAL_SERVER_ERROR
    return HTTPException(status_code=status_code, detail=message)


def _parse_tags(raw_value: str | None) -> list[str]:
    if not raw_value:
        return []
    return [tag.strip() for tag in raw_value.split(";") if tag.strip()]



def _deserialize_tags(raw_value: str | None) -> list[str]:
    if not raw_value:
        return []
    try:
        parsed = json.loads(raw_value)
        if isinstance(parsed, list):
            return [str(item) for item in parsed]
    except json.JSONDecodeError:
        logger.warning("Failed to decode tags JSON in router: %s", raw_value)
    return []



def _row_to_document(row: sqlite3.Row) -> DocumentResponse:
    return DocumentResponse(
        id=row["id"],
        category=row["category"],
        is_private=bool(row["is_private"]),
        title=row["title"],
        source=row["source"],
        content=row["content"],
        practical=row["practical"],
        date=row["date"],
        tags=_deserialize_tags(row["tags"]),
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )



def _insert_document_snapshot(connection: sqlite3.Connection, document: DocumentResponse) -> None:
    connection.execute(
        f"""
        INSERT OR REPLACE INTO {TABLE_NAME} (
            id, category, is_private, title, source, content, practical,
            date, tags, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            document.id,
            document.category,
            int(document.is_private),
            document.title,
            document.source,
            document.content,
            document.practical,
            document.date,
            json.dumps(document.tags, ensure_ascii=False),
            document.created_at.isoformat(),
            document.updated_at.isoformat(),
        ),
    )



def _list_documents_from_db(
    *,
    category: str | None = None,
    search: str | None = None,
    page: int = 1,
    page_size: int = 20,
    export_all: bool = False,
) -> dict[str, Any]:
    normalized_page = max(1, page)
    normalized_page_size = max(1, page_size)
    offset = (normalized_page - 1) * normalized_page_size

    filters: list[str] = []
    params: list[Any] = []

    if category:
        filters.append("category = ?")
        params.append(category)

    if search:
        keyword = f"%{search.strip()}%"
        filters.append(
            "("
            "title LIKE ? OR source LIKE ? OR content LIKE ? OR "
            "COALESCE(practical, '') LIKE ? OR tags LIKE ?"
            ")"
        )
        params.extend([keyword, keyword, keyword, keyword, keyword])

    where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""

    try:
        with closing(get_connection()) as connection:
            total = connection.execute(
                f"SELECT COUNT(*) FROM {TABLE_NAME} {where_clause}",
                params,
            ).fetchone()[0]

            query = (
                f"""
                SELECT *
                FROM {TABLE_NAME}
                {where_clause}
                ORDER BY updated_at DESC
                """
            )
            query_params = list(params)

            if not export_all:
                query += " LIMIT ? OFFSET ?"
                query_params.extend([normalized_page_size, offset])

            rows = connection.execute(query, query_params).fetchall()

        items = [_row_to_document(row).model_dump(mode="json") for row in rows]
        total_pages = (total + normalized_page_size - 1) // normalized_page_size if total else 0
        return {
            "items": items,
            "total": total,
            "page": normalized_page,
            "page_size": normalized_page_size,
            "total_pages": total_pages,
        }
    except sqlite3.Error as exc:
        logger.exception("Failed to list documents.")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="문서 목록 조회 중 오류가 발생했습니다.") from exc



def _decode_text_content(raw_bytes: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "cp949"):
        try:
            return raw_bytes.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="업로드 파일 인코딩을 읽을 수 없습니다.")



def _detect_bulk_upload_kind(filename: str) -> str:
    extension = Path(filename).suffix.lower()
    if extension == ".csv":
        return "csv"
    if extension in SUPPORTED_MARKDOWN_EXTENSIONS:
        return "markdown"
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="대량등록은 CSV(.csv) 또는 Markdown(.md) 파일만 지원합니다.",
    )



def _validate_csv_headers(headers: list[str] | None) -> None:
    if headers is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="CSV 헤더가 없습니다.")

    missing_headers = [header for header in CSV_HEADERS if header not in headers]
    if missing_headers:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"필수 CSV 헤더가 없습니다: {', '.join(missing_headers)}",
        )



def _validation_message_for_field(field_name: str) -> str:
    label_map = {
        "title": "제목",
        "source": "출처",
        "content": "내용",
        "date": "날짜",
        "category": "분류",
    }
    if field_name == "date":
        return "날짜는 YYYY-MM-DD 형식이어야 합니다."
    if field_name in {"title", "source", "content"}:
        return f"{label_map.get(field_name, field_name)} 값이 비어 있습니다."
    return f"{label_map.get(field_name, field_name)} 값이 올바르지 않습니다."



def _build_document_create_from_fields(raw: dict[str, str], source_label: str) -> DocumentCreate:
    category_label = (raw.get("분류") or "").strip()
    category = KOREAN_TO_CATEGORY.get(category_label)
    if category is None:
        raise ValueError(f"{source_label}의 분류 값이 올바르지 않습니다: {category_label}")

    try:
        return DocumentCreate(
            category=category,
            is_private=True,
            title=(raw.get("제목") or "").strip(),
            source=(raw.get("출처") or "").strip(),
            content=(raw.get("내용") or "").strip(),
            practical=(raw.get("전산적용") or "").strip() or None,
            date=(raw.get("날짜") or "").strip(),
            tags=_parse_tags(raw.get("태그")),
        )
    except ValidationError as exc:
        messages = []
        for issue in exc.errors():
            field_name = str(issue.get("loc", [""])[-1])
            messages.append(_validation_message_for_field(field_name))
        raise ValueError(f"{source_label} 입력값이 올바르지 않습니다. {' '.join(dict.fromkeys(messages))}") from exc



def _build_document_create_from_csv(row: dict[str, str], row_number: int) -> DocumentCreate:
    return _build_document_create_from_fields(row, f"{row_number}행")



def _strip_markdown_prefix(value: str) -> str:
    return re.sub(r"^\s*[-*]\s+", "", value).strip()


def _normalize_markdown_section_key(value: str) -> str:
    normalized = value.strip()
    for key in MARKDOWN_SECTION_KEYS:
        if normalized == key or normalized.startswith(f"{key}("):
            return key
    return normalized


def _extract_markdown_document_fields(block: str) -> dict[str, str]:
    raw_fields = {header: "" for header in CSV_HEADERS}
    body_lines: list[str] = []
    section_lines = {key: [] for key in MARKDOWN_SECTION_KEYS}
    current_section: str | None = None

    for raw_line in block.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()

        if not stripped:
            if current_section:
                section_lines[current_section].append("")
            elif body_lines and body_lines[-1] != "":
                body_lines.append("")
            continue

        normalized = _strip_markdown_prefix(stripped)

        if normalized.startswith("## "):
            heading = _normalize_markdown_section_key(normalized[3:].strip())
            if heading in MARKDOWN_SECTION_KEYS:
                current_section = heading
                continue

        key, separator, value = normalized.partition(":")
        key = _normalize_markdown_section_key(key.strip())
        if separator and key in MARKDOWN_SECTION_KEYS:
            current_section = key
            if value.strip():
                section_lines[key].append(value.strip())
            continue

        if current_section:
            section_lines[current_section].append(line)
            continue

        if normalized.startswith("# ") and not raw_fields["제목"]:
            raw_fields["제목"] = normalized[2:].strip()
            continue

        if separator and key in MARKDOWN_METADATA_KEYS:
            raw_fields[key] = value.strip()
            continue

        body_lines.append(line)

    raw_fields["내용"] = "\n".join(section_lines["내용"]).strip() or "\n".join(body_lines).strip()
    raw_fields["전산적용"] = "\n".join(section_lines["전산적용"]).strip()
    return raw_fields



def _parse_markdown_documents(decoded_content: str) -> list[dict[str, str]]:
    normalized = decoded_content.replace("\ufeff", "").strip()
    if not normalized:
        return []

    blocks = [block.strip() for block in re.split(r"(?m)^\s*---\s*$", normalized) if block.strip()]
    return [_extract_markdown_document_fields(block) for block in blocks]



def _build_document_create_from_markdown(row: dict[str, str], document_number: int) -> DocumentCreate:
    return _build_document_create_from_fields(row, f"{document_number}번 문서")


@router.post("", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
def create_document(document: DocumentCreate) -> DocumentResponse:
    try:
        return add_document(document)
    except StorageError as exc:
        raise _storage_http_exception(exc) from exc


@router.post("/bulk", status_code=status.HTTP_201_CREATED)
async def create_documents_bulk(file: UploadFile = File(...)) -> dict[str, Any]:
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="업로드 파일 이름이 없습니다.")

    raw_bytes = await file.read()
    if not raw_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="빈 파일은 업로드할 수 없습니다.")

    upload_kind = _detect_bulk_upload_kind(file.filename)
    decoded_content = _decode_text_content(raw_bytes)

    created_documents: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    processed_rows = 0

    if upload_kind == "csv":
        reader = csv.DictReader(io.StringIO(decoded_content))
        _validate_csv_headers(reader.fieldnames)

        for row_number, row in enumerate(reader, start=2):
            if not any((value or "").strip() for value in row.values()):
                continue

            processed_rows += 1
            try:
                payload = _build_document_create_from_csv(row, row_number)
                created = add_document(payload)
                created_documents.append(created.model_dump(mode="json"))
            except Exception as exc:
                errors.append(
                    {
                        "row": row_number,
                        "title": (row.get("제목") or "").strip(),
                        "error": str(exc),
                    }
                )
    else:
        markdown_documents = _parse_markdown_documents(decoded_content)
        for document_number, row in enumerate(markdown_documents, start=1):
            if not any((value or "").strip() for value in row.values()):
                continue

            processed_rows += 1
            try:
                payload = _build_document_create_from_markdown(row, document_number)
                created = add_document(payload)
                created_documents.append(created.model_dump(mode="json"))
            except Exception as exc:
                errors.append(
                    {
                        "row": document_number,
                        "title": (row.get("제목") or "").strip(),
                        "error": str(exc),
                    }
                )

    if processed_rows == 0:
        detail = "업로드할 데이터 행이 없습니다." if upload_kind == "csv" else "업로드할 Markdown 문서가 없습니다."
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)

    if not created_documents and errors:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": "일괄 등록에 실패했습니다.", "errors": errors},
        )

    return {
        "file_type": upload_kind,
        "total_rows": processed_rows,
        "created_count": len(created_documents),
        "failed_count": len(errors),
        "documents": created_documents,
        "errors": errors,
    }


@router.get("")
def list_documents(
    category: str | None = Query(default=None, description="영문 카테고리 필터"),
    search: str | None = Query(default=None, description="제목/출처/내용/전산적용/태그 검색어"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> dict[str, Any]:
    return _list_documents_from_db(
        category=category,
        search=search,
        page=page,
        page_size=page_size,
    )


@router.get("/export")
def export_documents(
    category: str | None = Query(default=None, description="영문 카테고리 필터"),
    search: str | None = Query(default=None, description="검색어"),
) -> StreamingResponse:
    result = _list_documents_from_db(
        category=category,
        search=search,
        export_all=True,
    )

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(CSV_HEADERS)

    for item in result["items"]:
        writer.writerow(
            [
                CATEGORY_TO_KOREAN.get(item["category"], item["category"]),
                item["title"],
                item["source"],
                item["content"],
                item["practical"] or "",
                item["date"],
                ";".join(item["tags"]),
            ]
        )

    filename = f"documents_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    csv_bytes = ("\ufeff" + output.getvalue()).encode("utf-8")
    return StreamingResponse(
        io.BytesIO(csv_bytes),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/stats")
def get_document_stats() -> dict[str, Any]:
    try:
        with closing(get_connection()) as connection:
            total_count = connection.execute(f"SELECT COUNT(*) FROM {TABLE_NAME}").fetchone()[0]
            with_practical_count = connection.execute(
                f"""
                SELECT COUNT(*)
                FROM {TABLE_NAME}
                WHERE practical IS NOT NULL AND TRIM(practical) <> ''
                """
            ).fetchone()[0]
            rows = connection.execute(
                f"""
                SELECT category, COUNT(*) AS count
                FROM {TABLE_NAME}
                GROUP BY category
                ORDER BY category
                """
            ).fetchall()
    except sqlite3.Error as exc:
        logger.exception("Failed to calculate document stats.")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="통계 조회 중 오류가 발생했습니다.") from exc

    return {
        "total_count": total_count,
        "with_practical_count": with_practical_count,
        "category_counts": {row["category"]: row["count"] for row in rows},
    }


@router.get("/{document_id}", response_model=DocumentResponse)
def get_document(document_id: str) -> DocumentResponse:
    try:
        document = get_document_by_id(document_id)
    except StorageError as exc:
        raise _storage_http_exception(exc) from exc

    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="문서를 찾을 수 없습니다.")

    return document


@router.put("/{document_id}", response_model=DocumentResponse)
def update_document_endpoint(document_id: str, document_update: DocumentUpdate) -> DocumentResponse:
    try:
        updated = update_document(document_id, document_update)
    except StorageError as exc:
        raise _storage_http_exception(exc) from exc

    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="문서를 찾을 수 없습니다.")

    return updated


@router.delete("/{document_id}")
def delete_document_endpoint(document_id: str) -> dict[str, str]:
    try:
        deleted = delete_document(document_id)
    except StorageError as exc:
        raise _storage_http_exception(exc) from exc

    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="문서를 찾을 수 없습니다.")

    return {"message": "문서가 삭제되었습니다."}


@router.delete("")
def delete_all_documents(confirm: str = Query(..., description="전체 삭제 확인용 문자열, DELETE_ALL")) -> dict[str, Any]:
    if confirm != "DELETE_ALL":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="confirm 파라미터는 DELETE_ALL 이어야 합니다.")

    try:
        with closing(get_connection()) as connection:
            rows = connection.execute(f"SELECT * FROM {TABLE_NAME}").fetchall()
            snapshots = [_row_to_document(row) for row in rows]
            deleted_count = len(snapshots)

            with connection:
                connection.execute(f"DELETE FROM {TABLE_NAME}")
    except sqlite3.Error as exc:
        logger.exception("Failed to delete all documents from SQLite.")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="SQLite 전체 삭제 중 오류가 발생했습니다.") from exc

    if not snapshots:
        return {"deleted_count": 0, "message": "삭제할 문서가 없습니다."}

    try:
        collection = get_collection()
        collection.delete(ids=[document.id for document in snapshots])
    except Exception as exc:
        logger.exception("Failed to delete all documents from ChromaDB. Restoring SQLite rows.")
        try:
            with closing(get_connection()) as connection:
                with connection:
                    for document in snapshots:
                        _insert_document_snapshot(connection, document)
        except sqlite3.Error:
            logger.exception("Failed to restore SQLite rows after ChromaDB delete failure.")
        raise _storage_http_exception(exc) from exc

    return {"deleted_count": deleted_count, "message": "모든 문서가 삭제되었습니다."}

