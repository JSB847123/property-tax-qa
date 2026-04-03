from __future__ import annotations

from pathlib import Path

import pytest

from app import runtime_settings


@pytest.fixture(autouse=True)
def isolated_runtime_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    settings_path = tmp_path / 'runtime_settings.json'
    monkeypatch.setattr(runtime_settings, 'DATA_DIR', tmp_path)
    monkeypatch.setattr(runtime_settings, 'SETTINGS_PATH', settings_path)
    monkeypatch.setattr(runtime_settings, 'ENV_PATH', tmp_path / '.env')
    monkeypatch.setattr(runtime_settings, '_runtime_overrides', {})
    for env_name in ('ANTHROPIC_API_KEY', 'OPENAI_API_KEY', 'GEMINI_API_KEY', 'GLM_API_KEY', 'LAW_OC', 'LLM_PROVIDER'):
        monkeypatch.delenv(env_name, raising=False)
    return settings_path


def test_session_settings_are_applied_without_persistence() -> None:
    status = runtime_settings.update_settings(anthropic_api_key='temp-anthropic-key', llm_provider='anthropic', persist=False)

    assert status['anthropic']['configured'] is True
    assert status['anthropic']['source'] == 'memory'
    assert status['anthropic']['saved'] is False
    assert status['llm_provider']['active'] == 'anthropic'
    assert runtime_settings.get_anthropic_api_key() == 'temp-anthropic-key'
    assert runtime_settings.SETTINGS_PATH.exists() is False


def test_saved_settings_are_persisted_to_file() -> None:
    status = runtime_settings.update_settings(openai_api_key='saved-openai-key', law_oc='saved-law-oc', llm_provider='openai', persist=True)

    assert status['openai']['configured'] is True
    assert status['openai']['source'] == 'file'
    assert status['openai']['saved'] is True
    assert status['law_oc']['configured'] is True
    assert status['llm_provider']['active'] == 'openai'
    assert runtime_settings.get_openai_api_key() == 'saved-openai-key'
    assert runtime_settings.get_law_oc() == 'saved-law-oc'
    assert runtime_settings.SETTINGS_PATH.exists() is True
    persisted = runtime_settings.SETTINGS_PATH.read_text(encoding='utf-8')
    assert 'saved-openai-key' in persisted
    assert 'saved-law-oc' in persisted
    assert 'openai' in persisted


def test_runtime_override_beats_saved_value_until_cleared() -> None:
    runtime_settings.update_settings(anthropic_api_key='saved-key', llm_provider='anthropic', persist=True)
    runtime_settings.update_settings(openai_api_key='session-openai-key', llm_provider='openai', persist=False)

    status = runtime_settings.get_settings_status()
    assert status['openai']['source'] == 'memory'
    assert status['llm_provider']['active'] == 'openai'
    assert runtime_settings.get_openai_api_key() == 'session-openai-key'

    cleared = runtime_settings.clear_runtime_overrides()
    assert cleared['llm_provider']['active'] == 'anthropic'
    assert runtime_settings.get_anthropic_api_key() == 'saved-key'


def test_env_value_is_used_as_last_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('LAW_OC', 'env-law-oc')
    monkeypatch.setenv('GEMINI_API_KEY', 'env-gemini-key')

    status = runtime_settings.get_settings_status()

    assert status['law_oc']['configured'] is True
    assert status['law_oc']['source'] == 'env'
    assert status['gemini']['configured'] is True
    assert status['llm_provider']['active'] == 'gemini'
    assert runtime_settings.get_law_oc() == 'env-law-oc'
    assert runtime_settings.get_gemini_api_key() == 'env-gemini-key'


def test_invalid_provider_is_rejected() -> None:
    with pytest.raises(ValueError):
        runtime_settings.update_settings(llm_provider='invalid-provider', persist=False)
