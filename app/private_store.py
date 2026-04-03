from __future__ import annotations

import json
import logging
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

try:
    import chromadb
    from chromadb.utils import embedding_functions
except ImportError:  # pragma: no cover - dependency may not be installed yet
    chromadb = None  # type: ignore[assignment]
    embedding_functions = None  # type: ignore[assignment]

from app.database import DATA_DIR, TABLE_NAME, get_connection, init_db
from app.models import DocumentCreate, DocumentResponse, DocumentUpdate


logger = logging.getLogger(__name__)

CHROMA_PATH = DATA_DIR / "chroma"
CHROMA_DIR = CHROMA_PATH
COLLECTION_NAME = "private_documents"
REQUIRED_FIELDS = {"category", "is_private", "title", "source", "content", "date"}

_chroma_client: Any | None = None
_collection: Any | None = None


class StorageError(Exception):
    """Raised when SQLite or ChromaDB storage operations fail."""


def _ensure_storage_paths() -> None:
    init_db()
    CHROMA_PATH.mkdir(parents=True, exist_ok=True)


def get_collection() -> Any:
    global _chroma_client, _collection

    if _collection is not None:
        return _collection

    if chromadb is None or embedding_functions is None:
        raise StorageError("chromadb is not installed. Install requirements.txt dependencies first.")

    try:
        _ensure_storage_paths()
        if _chroma_client is None:
            _chroma_client = chromadb.PersistentClient(path=str(CHROMA_PATH))
        _collection = _chroma_client.get_or_create_collection(
            name=COLLECTION_NAME,
            embedding_function=embedding_functions.DefaultEmbeddingFunction(),
            metadata={"hnsw:space": "cosine"},
        )
        return _collection
    except Exception as exc:
        logger.exception("Failed to initialize ChromaDB collection at %s", CHROMA_PATH)
        raise StorageError("Failed to initialize ChromaDB collection.") from exc


def _safe_get_collection() -> Any | None:
    try:
        return get_collection()
    except StorageError as exc:
        logger.warning("ChromaDB unavailable. Falling back to SQLite-only mode: %s", exc)
        return None


def _serialize_tags(tags: list[str]) -> str:
    return json.dumps(tags, ensure_ascii=False)


def _deserialize_tags(tags: str | None) -> list[str]:
    if not tags:
        return []

    try:
        decoded = json.loads(tags)
        if isinstance(decoded, list):
            return [str(item) for item in decoded]
    except json.JSONDecodeError:
        logger.warning("Failed to decode tags JSON: %s", tags)
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


def _document_to_metadata(document: DocumentResponse) -> dict[str, Any]:
    return {
        "category": document.category,
        "is_private": document.is_private,
        "title": document.title,
        "source": document.source,
        "date": document.date,
        "tags": _serialize_tags(document.tags),
        "practical": document.practical or "",
        "updated_at": document.updated_at.isoformat(),
    }


def _document_to_embedding_text(document: DocumentResponse) -> str:
    parts = [
        f"제목: {document.title}",
        f"카테고리: {document.category}",
        f"출처: {document.source}",
        f"날짜: {document.date}",
        f"본문: {document.content}",
    ]
    if document.practical:
        parts.append(f"실무 적용: {document.practical}")
    if document.tags:
        parts.append(f"태그: {', '.join(document.tags)}")
    return "\n".join(parts)


def _tokenize_query(query: str) -> list[str]:
    return [token.strip().lower() for token in query.split() if token.strip()]


def _field_score(value: str | None, query_text: str, tokens: list[str], *, exact_weight: int, token_weight: int) -> int:
    normalized = (value or "").lower()
    if not normalized:
        return 0
    return normalized.count(query_text) * exact_weight + sum(normalized.count(token) * token_weight for token in tokens)


def _search_similar_sqlite(query: str, category: str | None = None, top_k: int = 5) -> list[dict[str, Any]]:
    query_text = query.strip().lower()
    tokens = _tokenize_query(query)
    if not query_text or not tokens:
        return []

    filters: list[str] = []
    params: list[Any] = []
    if category:
        filters.append("category = ?")
        params.append(category)

    where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""

    try:
        with closing(get_connection()) as connection:
            rows = connection.execute(
                f"""
                SELECT *
                FROM {TABLE_NAME}
                {where_clause}
                ORDER BY updated_at DESC
                """,
                params,
            ).fetchall()
    except sqlite3.Error as exc:
        logger.exception("Failed to search similar documents in SQLite fallback.")
        raise StorageError("Failed to search similar documents.") from exc

    ranked: list[tuple[int, dict[str, Any]]] = []
    for row in rows:
        document = _row_to_document(row)
        tags_text = " ".join(document.tags)
        score = 0
        score += _field_score(document.title, query_text, tokens, exact_weight=30, token_weight=8)
        score += _field_score(document.content, query_text, tokens, exact_weight=18, token_weight=4)
        score += _field_score(document.practical, query_text, tokens, exact_weight=16, token_weight=5)
        score += _field_score(document.source, query_text, tokens, exact_weight=8, token_weight=2)
        score += _field_score(tags_text, query_text, tokens, exact_weight=12, token_weight=6)
        score += _field_score(document.category, query_text, tokens, exact_weight=6, token_weight=1)
        if score <= 0:
            continue

        payload = document.model_dump(mode="json")
        payload["distance"] = round(1 / (score + 1), 6)
        ranked.append((score, payload))

    ranked.sort(key=lambda item: item[0], reverse=True)
    return [payload for _, payload in ranked[: max(1, top_k)]]


def _insert_or_replace_document(connection: sqlite3.Connection, document: DocumentResponse) -> None:
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
            _serialize_tags(document.tags),
            document.created_at.isoformat(),
            document.updated_at.isoformat(),
        ),
    )


def _delete_sqlite_document(document_id: str) -> None:
    with closing(get_connection()) as connection:
        with connection:
            connection.execute(f"DELETE FROM {TABLE_NAME} WHERE id = ?", (document_id,))


def _fetch_document_map(ids: list[str]) -> dict[str, DocumentResponse]:
    if not ids:
        return {}

    placeholders = ", ".join("?" for _ in ids)
    query = f"SELECT * FROM {TABLE_NAME} WHERE id IN ({placeholders})"

    try:
        with closing(get_connection()) as connection:
            rows = connection.execute(query, ids).fetchall()
        return {row["id"]: _row_to_document(row) for row in rows}
    except sqlite3.Error as exc:
        logger.exception("Failed to fetch documents by ids.")
        raise StorageError("Failed to fetch documents from SQLite.") from exc


def add_document(document: DocumentCreate | dict[str, Any]) -> DocumentResponse:
    payload = document if isinstance(document, DocumentCreate) else DocumentCreate.model_validate(document)
    now = datetime.now(timezone.utc)
    stored_document = DocumentResponse(
        id=str(uuid4()),
        category=payload.category,
        is_private=payload.is_private,
        title=payload.title,
        source=payload.source,
        content=payload.content,
        practical=payload.practical,
        date=payload.date,
        tags=payload.tags,
        created_at=now,
        updated_at=now,
    )

    try:
        with closing(get_connection()) as connection:
            with connection:
                _insert_or_replace_document(connection, stored_document)
    except sqlite3.Error as exc:
        logger.exception("Failed to insert document into SQLite.")
        raise StorageError("Failed to save document to SQLite.") from exc

    collection = _safe_get_collection()
    if collection is None:
        return stored_document

    try:
        collection.add(
            ids=[stored_document.id],
            documents=[_document_to_embedding_text(stored_document)],
            metadatas=[_document_to_metadata(stored_document)],
        )
    except Exception:
        logger.exception("Failed to add document to ChromaDB. Document remains stored in SQLite.")
    return stored_document


def update_document(document_id: str, document_update: DocumentUpdate | dict[str, Any]) -> DocumentResponse | None:
    existing = get_document_by_id(document_id)
    if existing is None:
        return None

    payload = document_update if isinstance(document_update, DocumentUpdate) else DocumentUpdate.model_validate(document_update)
    updates = payload.model_dump(exclude_unset=True)

    if not updates:
        return existing

    for field in REQUIRED_FIELDS:
        if field in updates and updates[field] is None:
            raise StorageError(f"Field '{field}' cannot be null.")

    if "tags" in updates and updates["tags"] is None:
        updates["tags"] = []

    updated_document = existing.model_copy(
        update={
            **updates,
            "updated_at": datetime.now(timezone.utc),
        }
    )

    try:
        with closing(get_connection()) as connection:
            with connection:
                _insert_or_replace_document(connection, updated_document)
    except sqlite3.Error as exc:
        logger.exception("Failed to update document %s in SQLite.", document_id)
        raise StorageError("Failed to update document in SQLite.") from exc

    collection = _safe_get_collection()
    if collection is None:
        return updated_document

    try:
        collection.upsert(
            ids=[updated_document.id],
            documents=[_document_to_embedding_text(updated_document)],
            metadatas=[_document_to_metadata(updated_document)],
        )
    except Exception:
        logger.exception("Failed to update document %s in ChromaDB. SQLite remains the source of truth.", document_id)
    return updated_document


def delete_document(document_id: str) -> bool:
    existing = get_document_by_id(document_id)
    if existing is None:
        return False

    try:
        _delete_sqlite_document(document_id)
    except sqlite3.Error as exc:
        logger.exception("Failed to delete document %s from SQLite.", document_id)
        raise StorageError("Failed to delete document from SQLite.") from exc

    collection = _safe_get_collection()
    if collection is None:
        return True

    try:
        collection.delete(ids=[document_id])
    except Exception:
        logger.exception("Failed to delete document %s from ChromaDB. SQLite row is already removed.", document_id)
    return True


def search_similar(query: str, category: str | None = None, top_k: int = 5) -> list[dict[str, Any]]:
    if not query or not query.strip():
        return []

    collection = _safe_get_collection()
    if collection is not None:
        try:
            if collection.count() > 0:
                query_kwargs: dict[str, Any] = {
                    "query_texts": [query],
                    "n_results": max(1, top_k),
                    "include": ["documents", "metadatas", "distances"],
                }
                if category:
                    query_kwargs["where"] = {"category": category}

                result = collection.query(**query_kwargs)
                ids = result.get("ids", [[]])[0]
                distances = result.get("distances", [[]])[0]
                indexed_documents = _fetch_document_map(ids)

                matches: list[dict[str, Any]] = []
                for index, document_id in enumerate(ids):
                    document = indexed_documents.get(document_id)
                    if document is None:
                        continue

                    payload = document.model_dump(mode="json")
                    payload["distance"] = distances[index] if index < len(distances) else None
                    matches.append(payload)
                if matches:
                    return matches
        except StorageError:
            raise
        except Exception:
            logger.exception("Failed to search similar documents in ChromaDB. Falling back to SQLite search.")

    return _search_similar_sqlite(query, category, top_k)


def get_all_documents(
    category: str | None = None,
    is_private: bool | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    normalized_page = max(1, page)
    normalized_page_size = max(1, page_size)
    offset = (normalized_page - 1) * normalized_page_size

    filters: list[str] = []
    params: list[Any] = []

    if category:
        filters.append("category = ?")
        params.append(category)
    if is_private is not None:
        filters.append("is_private = ?")
        params.append(int(is_private))

    where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""

    try:
        with closing(get_connection()) as connection:
            total = connection.execute(
                f"SELECT COUNT(*) FROM {TABLE_NAME} {where_clause}",
                params,
            ).fetchone()[0]
            rows = connection.execute(
                f"""
                SELECT *
                FROM {TABLE_NAME}
                {where_clause}
                ORDER BY updated_at DESC
                LIMIT ? OFFSET ?
                """,
                [*params, normalized_page_size, offset],
            ).fetchall()

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
        logger.exception("Failed to list documents from SQLite.")
        raise StorageError("Failed to list documents.") from exc


def get_document_by_id(document_id: str) -> DocumentResponse | None:
    try:
        with closing(get_connection()) as connection:
            row = connection.execute(
                f"SELECT * FROM {TABLE_NAME} WHERE id = ?",
                (document_id,),
            ).fetchone()
        return _row_to_document(row) if row else None
    except sqlite3.Error as exc:
        logger.exception("Failed to fetch document %s from SQLite.", document_id)
        raise StorageError("Failed to fetch document.") from exc
