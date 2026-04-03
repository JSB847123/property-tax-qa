from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import database
from app.favorite_sources import build_favorite_id
from app.main import app


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    temp_db_path = tmp_path / 'tax_rag_test.db'

    monkeypatch.setattr(database, 'DATA_DIR', tmp_path)
    monkeypatch.setattr(database, 'DATABASE_PATH', temp_db_path)
    monkeypatch.setattr(database, 'DB_PATH', temp_db_path)
    database.init_db()

    with TestClient(app) as test_client:
        yield test_client


def test_create_list_and_delete_favorite_source(client: TestClient) -> None:
    payload = {
        'category': 'precedent',
        'source_type': 'precedent',
        'title': '대법원 2021다299976, 299983',
        'source': '대법원 2022.09.29.',
        'reference': '2021다299976, 299983',
        'detail_link': 'https://www.law.go.kr/DRF/lawService.do?target=prec&ID=231453&type=HTML',
        'summary': '부담부증여에도 증여 일반 조항이 적용된다는 점을 정리한 판결이다.',
        'date': '2022-09-29',
    }

    create_response = client.post('/api/favorites', json=payload)

    assert create_response.status_code == 201
    created = create_response.json()
    assert created['favorite_id'] == build_favorite_id(payload)
    assert created['title'] == payload['title']

    list_response = client.get('/api/favorites')

    assert list_response.status_code == 200
    items = list_response.json()
    assert len(items) == 1
    assert items[0]['favorite_id'] == created['favorite_id']

    delete_response = client.delete(f"/api/favorites/{created['favorite_id']}")

    assert delete_response.status_code == 204
    assert client.get('/api/favorites').json() == []


def test_reposting_same_source_updates_existing_favorite_without_duplication(client: TestClient) -> None:
    payload = {
        'category': 'tribunal',
        'source_type': 'tribunal',
        'title': '조심2020지1234',
        'source': '조세심판원 2021.01.21.',
        'reference': '조심2020지1234',
        'detail_link': 'https://www.law.go.kr/DRF/lawService.do?target=admrul&ID=90604&type=HTML',
        'summary': '원래 요약',
        'date': '2021-01-21',
    }

    first = client.post('/api/favorites', json=payload)
    second = client.post('/api/favorites', json={**payload, 'summary': '수정된 요약'})

    assert first.status_code == 201
    assert second.status_code == 201

    items = client.get('/api/favorites').json()
    assert len(items) == 1
    assert items[0]['favorite_id'] == build_favorite_id(payload)
    assert items[0]['summary'] == '수정된 요약'


def test_delete_unknown_favorite_returns_not_found(client: TestClient) -> None:
    response = client.delete('/api/favorites/fav_missing')

    assert response.status_code == 404
    assert response.json()['detail'] == '해당 즐겨찾기를 찾지 못했습니다.'
