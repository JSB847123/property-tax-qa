from __future__ import annotations

import io
import json
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from pydantic import ValidationError

from app.favorites_store import clear_favorites, list_favorites, save_favorite_snapshot
from app.models import DocumentResponse, FavoriteSourceResponse
from app.private_store import clear_all_documents, list_all_documents, upsert_document_snapshot
from app.runtime_settings import export_settings_snapshot, import_settings_snapshot, normalize_settings_snapshot


router = APIRouter(prefix='/api/backup', tags=['backup'])

BACKUP_VERSION = 1


@router.get('/export')
def export_backup() -> StreamingResponse:
    payload = {
        'app': 'tax-rag',
        'version': BACKUP_VERSION,
        'exported_at': datetime.now(timezone.utc).isoformat(),
        'documents': [document.model_dump(mode='json') for document in list_all_documents()],
        'favorites': list_favorites(),
        'settings': export_settings_snapshot(),
    }

    filename = f"tax_rag_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    content = json.dumps(payload, ensure_ascii=False, indent=2).encode('utf-8')
    return StreamingResponse(
        io.BytesIO(content),
        media_type='application/json; charset=utf-8',
        headers={'Content-Disposition': f'attachment; filename="{filename}"'},
    )


@router.post('/import')
async def import_backup(
    file: UploadFile = File(...),
    mode: Literal['merge', 'replace'] = Form(default='merge'),
) -> dict[str, object]:
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='업로드 파일 이름이 없습니다.')

    raw_bytes = await file.read()
    if not raw_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='빈 백업 파일은 불러올 수 없습니다.')

    try:
        payload = json.loads(raw_bytes.decode('utf-8-sig'))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='백업 파일은 UTF-8 JSON 형식이어야 합니다.') from exc

    if not isinstance(payload, dict):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='백업 파일 형식이 올바르지 않습니다.')

    documents_raw = payload.get('documents') or []
    favorites_raw = payload.get('favorites') or []
    settings_raw = payload.get('settings') or {}

    if not isinstance(documents_raw, list) or not isinstance(favorites_raw, list):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='백업 파일 목록 형식이 올바르지 않습니다.')

    try:
        documents = [DocumentResponse.model_validate(item) for item in documents_raw]
        favorites = [FavoriteSourceResponse.model_validate(item) for item in favorites_raw]
        settings_snapshot = normalize_settings_snapshot(settings_raw)
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f'백업 파일 검증에 실패했습니다: {exc.errors()[0]["msg"]}') from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if mode == 'replace':
        clear_all_documents()
        clear_favorites()

    for document in documents:
        upsert_document_snapshot(document)

    for favorite in favorites:
        save_favorite_snapshot(favorite.model_dump(mode='json'))

    settings_status = import_settings_snapshot(settings_snapshot, replace=mode == 'replace')

    return {
        'message': '백업 파일을 복원했습니다.' if mode == 'merge' else '현재 데이터를 백업 파일 기준으로 교체했습니다.',
        'mode': mode,
        'documents_imported': len(documents),
        'favorites_imported': len(favorites),
        'settings_imported': len(settings_snapshot),
        'settings': settings_status,
    }
