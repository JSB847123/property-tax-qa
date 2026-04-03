from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.database import FAVORITES_TABLE_NAME, get_connection
from app.favorite_sources import normalize_favorite_source
from app.models import FavoriteSourceInput


def _row_to_favorite(row: Any) -> dict[str, Any]:
    return {
        "favorite_id": row["favorite_id"],
        "id": row["source_id"],
        "category": row["category"],
        "source_type": row["source_type"] or row["category"],
        "is_private": bool(row["is_private"]),
        "title": row["title"],
        "source": row["source"],
        "reference": row["reference"],
        "citation": row["citation"],
        "detail_link": row["detail_link"],
        "summary": row["summary"],
        "date": row["date"],
        "created_at": row["created_at"],
    }


def list_favorites() -> list[dict[str, Any]]:
    with get_connection() as connection:
        rows = connection.execute(
            f"SELECT favorite_id, source_id, category, source_type, is_private, title, source, reference, citation, detail_link, summary, date, created_at "
            f"FROM {FAVORITES_TABLE_NAME} ORDER BY created_at DESC"
        ).fetchall()
    return [_row_to_favorite(row) for row in rows]


def save_favorite(payload: FavoriteSourceInput | dict[str, Any]) -> dict[str, Any]:
    source_data = payload.model_dump() if isinstance(payload, FavoriteSourceInput) else dict(payload)
    normalized = normalize_favorite_source(source_data)

    with get_connection() as connection:
        existing = connection.execute(
            f"SELECT created_at FROM {FAVORITES_TABLE_NAME} WHERE favorite_id = ?",
            (normalized["favorite_id"],),
        ).fetchone()
        created_at = existing["created_at"] if existing else datetime.now(timezone.utc).isoformat()

        with connection:
            connection.execute(
                f"""
                INSERT INTO {FAVORITES_TABLE_NAME} (
                    favorite_id, source_id, category, source_type, is_private, title, source,
                    reference, citation, detail_link, summary, date, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(favorite_id) DO UPDATE SET
                    source_id = excluded.source_id,
                    category = excluded.category,
                    source_type = excluded.source_type,
                    is_private = excluded.is_private,
                    title = excluded.title,
                    source = excluded.source,
                    reference = excluded.reference,
                    citation = excluded.citation,
                    detail_link = excluded.detail_link,
                    summary = excluded.summary,
                    date = excluded.date
                """,
                (
                    normalized["favorite_id"],
                    normalized["id"],
                    normalized["category"],
                    normalized["source_type"],
                    1 if normalized["is_private"] else 0,
                    normalized["title"],
                    normalized["source"],
                    normalized["reference"],
                    normalized["citation"],
                    normalized["detail_link"],
                    normalized["summary"],
                    normalized["date"],
                    created_at,
                ),
            )

        row = connection.execute(
            f"SELECT favorite_id, source_id, category, source_type, is_private, title, source, reference, citation, detail_link, summary, date, created_at "
            f"FROM {FAVORITES_TABLE_NAME} WHERE favorite_id = ?",
            (normalized["favorite_id"],),
        ).fetchone()

    return _row_to_favorite(row)


def delete_favorite(favorite_id: str) -> bool:
    with get_connection() as connection:
        with connection:
            cursor = connection.execute(
                f"DELETE FROM {FAVORITES_TABLE_NAME} WHERE favorite_id = ?",
                (favorite_id,),
            )
    return cursor.rowcount > 0
