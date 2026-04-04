from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import database, private_store, runtime_settings
from app.favorite_sources import build_favorite_id
from app.favorites_store import save_favorite
from app.main import app
from app.models import DocumentCreate


class FakeCollection:
    def __init__(self) -> None:
        self._items: dict[str, dict[str, Any]] = {}

    def add(self, ids: list[str], documents: list[str], metadatas: list[dict[str, Any]]) -> None:
        for item_id, document, metadata in zip(ids, documents, metadatas, strict=False):
            self._items[item_id] = {'document': document, 'metadata': metadata}

    def upsert(self, ids: list[str], documents: list[str], metadatas: list[dict[str, Any]]) -> None:
        self.add(ids, documents, metadatas)

    def delete(self, ids: list[str]) -> None:
        for item_id in ids:
            self._items.pop(item_id, None)

    def count(self) -> int:
        return len(self._items)


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    temp_db_path = tmp_path / 'tax_rag_test.db'
    settings_path = tmp_path / 'runtime_settings.json'
    fake_collection = FakeCollection()

    monkeypatch.setattr(database, 'DATA_DIR', tmp_path)
    monkeypatch.setattr(database, 'DATABASE_PATH', temp_db_path)
    monkeypatch.setattr(database, 'DB_PATH', temp_db_path)
    monkeypatch.setattr(private_store, 'CHROMA_PATH', tmp_path / 'chroma')
    monkeypatch.setattr(private_store, 'CHROMA_DIR', tmp_path / 'chroma')
    monkeypatch.setattr(private_store, '_collection', None)
    monkeypatch.setattr(private_store, '_chroma_client', None)
    monkeypatch.setattr(private_store, 'get_collection', lambda: fake_collection)
    monkeypatch.setattr(runtime_settings, 'DATA_DIR', tmp_path)
    monkeypatch.setattr(runtime_settings, 'SETTINGS_PATH', settings_path)
    monkeypatch.setattr(runtime_settings, 'ENV_PATH', tmp_path / '.env')
    monkeypatch.setattr(runtime_settings, '_runtime_overrides', {})

    for env_name in ('ANTHROPIC_API_KEY', 'OPENAI_API_KEY', 'GEMINI_API_KEY', 'GLM_API_KEY', 'LAW_OC', 'LLM_PROVIDER'):
        monkeypatch.delenv(env_name, raising=False)

    database.init_db()

    with TestClient(app) as test_client:
        yield test_client


def _sample_document_payload(title: str, source: str, date: str) -> dict[str, Any]:
    document = private_store.add_document(
        DocumentCreate(
            category='case',
            is_private=True,
            title=title,
            source=source,
            content=f'{title}에 대한 설명 본문입니다.',
            practical='복원 테스트용 전산 메모',
            date=date,
            tags=['백업', '복원'],
        )
    )
    return document.model_dump(mode='json')


def _sample_favorite_payload(title: str, reference: str, date: str) -> dict[str, Any]:
    payload = {
        'category': 'precedent',
        'source_type': 'precedent',
        'title': title,
        'source': '대법원 2022.09.29.',
        'reference': reference,
        'detail_link': 'https://www.law.go.kr/DRF/lawService.do?target=prec&ID=231453&type=HTML',
        'summary': f'{title} 요약',
        'date': date,
    }
    favorite = save_favorite(payload)
    return favorite


def test_export_backup_contains_documents_favorites_and_settings(client: TestClient) -> None:
    document = _sample_document_payload('경매취득', '지방세운영과-2590', '2026-04-05')
    favorite = _sample_favorite_payload('대법원 2021다299976', '2021다299976', '2022-09-29')
    runtime_settings.update_settings(openai_api_key='backup-openai-key', law_oc='backup-law-oc', llm_provider='openai', persist=True)

    response = client.get('/api/backup/export')

    assert response.status_code == 200
    assert 'attachment; filename=' in response.headers['content-disposition']

    payload = json.loads(response.content.decode('utf-8'))
    assert payload['version'] == 1
    assert payload['documents'][0]['id'] == document['id']
    assert payload['favorites'][0]['favorite_id'] == favorite['favorite_id']
    assert payload['settings']['OPENAI_API_KEY'] == 'backup-openai-key'
    assert payload['settings']['LAW_OC'] == 'backup-law-oc'
    assert payload['settings']['LLM_PROVIDER'] == 'openai'


def test_import_backup_merge_restores_data_without_clearing_existing_rows(client: TestClient) -> None:
    pytest.importorskip('multipart')

    existing_document = _sample_document_payload('기존 문서', '기존 출처', '2026-04-04')

    backup_payload = {
        'app': 'tax-rag',
        'version': 1,
        'documents': [
            {
                'id': 'backup-doc-1',
                'category': 'civil',
                'is_private': True,
                'title': '복원 문서',
                'source': '백업 출처',
                'content': '백업 파일에서 복원된 문서입니다.',
                'practical': '복원 테스트',
                'date': '2026-04-05',
                'tags': ['복원'],
                'created_at': '2026-04-05T00:00:00+00:00',
                'updated_at': '2026-04-05T00:00:00+00:00',
            }
        ],
        'favorites': [
            {
                'favorite_id': build_favorite_id({'category': 'precedent', 'source_type': 'precedent', 'title': '복원 판례', 'source': '대법원 2022.09.29.', 'reference': '2021다299976', 'detail_link': 'https://example.com', 'date': '2022-09-29'}),
                'id': None,
                'category': 'precedent',
                'source_type': 'precedent',
                'is_private': False,
                'title': '복원 판례',
                'source': '대법원 2022.09.29.',
                'reference': '2021다299976',
                'citation': None,
                'detail_link': 'https://example.com',
                'summary': '복원 판례 요약',
                'date': '2022-09-29',
                'created_at': '2026-04-05T00:00:00+00:00',
            }
        ],
        'settings': {
            'OPENAI_API_KEY': 'restored-openai-key',
            'LAW_OC': 'restored-law-oc',
            'LLM_PROVIDER': 'openai',
        },
    }

    response = client.post(
        '/api/backup/import',
        data={'mode': 'merge'},
        files={'file': ('backup.json', json.dumps(backup_payload).encode('utf-8'), 'application/json')},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload['documents_imported'] == 1
    assert payload['favorites_imported'] == 1
    assert payload['settings_imported'] == 3

    documents = client.get('/api/documents').json()
    assert documents['total'] == 2
    assert {item['id'] for item in documents['items']} == {existing_document['id'], 'backup-doc-1'}

    favorites = client.get('/api/favorites').json()
    assert len(favorites) == 1
    assert favorites[0]['title'] == '복원 판례'
    assert runtime_settings.get_openai_api_key() == 'restored-openai-key'
    assert runtime_settings.get_law_oc() == 'restored-law-oc'


def test_import_backup_replace_swaps_existing_data(client: TestClient) -> None:
    pytest.importorskip('multipart')

    _sample_document_payload('기존 문서', '기존 출처', '2026-04-04')
    _sample_favorite_payload('기존 판례', '2020다111111', '2020-01-21')
    runtime_settings.update_settings(anthropic_api_key='old-anthropic-key', law_oc='old-law-oc', llm_provider='anthropic', persist=True)

    replacement_payload = {
        'app': 'tax-rag',
        'version': 1,
        'documents': [
            {
                'id': 'replacement-doc-1',
                'category': 'theory',
                'is_private': True,
                'title': '교체 문서',
                'source': '교체 출처',
                'content': '현재 자료를 대체할 문서입니다.',
                'practical': None,
                'date': '2026-04-05',
                'tags': ['교체'],
                'created_at': '2026-04-05T01:00:00+00:00',
                'updated_at': '2026-04-05T01:00:00+00:00',
            }
        ],
        'favorites': [
            {
                'favorite_id': 'fav_replace_case',
                'id': None,
                'category': 'tribunal',
                'source_type': 'tribunal',
                'is_private': False,
                'title': '교체 심판례',
                'source': '조세심판원 2024.01.10.',
                'reference': '조심2024지1000',
                'citation': None,
                'detail_link': 'https://example.com/tribunal',
                'summary': '교체 심판례 요약',
                'date': '2024-01-10',
                'created_at': '2026-04-05T01:00:00+00:00',
            }
        ],
        'settings': {
            'GEMINI_API_KEY': 'replacement-gemini-key',
            'LAW_OC': 'replacement-law-oc',
            'LLM_PROVIDER': 'gemini',
        },
    }

    response = client.post(
        '/api/backup/import',
        data={'mode': 'replace'},
        files={'file': ('backup.json', json.dumps(replacement_payload).encode('utf-8'), 'application/json')},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload['mode'] == 'replace'
    assert payload['documents_imported'] == 1
    assert payload['favorites_imported'] == 1
    assert payload['settings_imported'] == 3

    documents = client.get('/api/documents').json()
    assert documents['total'] == 1
    assert documents['items'][0]['title'] == '교체 문서'

    favorites = client.get('/api/favorites').json()
    assert len(favorites) == 1
    assert favorites[0]['title'] == '교체 심판례'
    assert runtime_settings.get_gemini_api_key() == 'replacement-gemini-key'
    assert runtime_settings.get_law_oc() == 'replacement-law-oc'
    assert runtime_settings.get_llm_provider() == 'gemini'
