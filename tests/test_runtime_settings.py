from __future__ import annotations

from pathlib import Path

import pytest

from app import runtime_settings


SETTING_CASES = [
    ('anthropic_api_key', 'anthropic', 'get_anthropic_api_key'),
    ('openai_api_key', 'openai', 'get_openai_api_key'),
    ('gemini_api_key', 'gemini', 'get_gemini_api_key'),
    ('glm_api_key', 'glm', 'get_glm_api_key'),
    ('law_oc', 'law_oc', 'get_law_oc'),
]


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


@pytest.mark.parametrize(('persist', 'expected_source', 'expected_saved'), [(False, 'memory', False), (True, 'file', True)])
@pytest.mark.parametrize(('payload_key', 'status_key', 'getter_name'), SETTING_CASES)
def test_each_setting_can_be_updated_individually(
    payload_key: str,
    status_key: str,
    getter_name: str,
    persist: bool,
    expected_source: str,
    expected_saved: bool,
) -> None:
    value = f'{status_key}-configured-value'

    status = runtime_settings.update_settings(persist=persist, **{payload_key: value})

    assert status[status_key]['configured'] is True
    assert status[status_key]['source'] == expected_source
    assert status[status_key]['saved'] is expected_saved
    getter = getattr(runtime_settings, getter_name)
    assert getter() == value


def test_provider_is_unset_when_no_key_or_selection_exists() -> None:
    status = runtime_settings.get_settings_status()

    assert runtime_settings.get_llm_provider() == ''
    assert status['llm_provider']['active'] is None
    assert status['llm_provider']['configured'] is False
    assert status['llm_provider']['selected'] is None


@pytest.mark.parametrize(('persist', 'expected_source', 'expected_saved'), [(False, 'memory', False), (True, 'file', True)])
@pytest.mark.parametrize('provider', ['anthropic', 'openai', 'gemini', 'glm'])
def test_provider_can_be_selected_individually(provider: str, persist: bool, expected_source: str, expected_saved: bool) -> None:
    status = runtime_settings.update_settings(llm_provider=provider, persist=persist)

    assert status['llm_provider']['active'] == provider
    assert status['llm_provider']['configured'] is False
    assert status['llm_provider']['selected'] == provider
    assert status['llm_provider']['source'] == expected_source
    assert status['llm_provider']['saved'] is expected_saved


def test_individual_saved_updates_preserve_existing_values() -> None:
    runtime_settings.update_settings(openai_api_key='saved-openai-key', persist=True)
    runtime_settings.update_settings(law_oc='saved-law-oc', persist=True)

    status = runtime_settings.get_settings_status()

    assert runtime_settings.get_openai_api_key() == 'saved-openai-key'
    assert runtime_settings.get_law_oc() == 'saved-law-oc'
    assert status['openai']['configured'] is True
    assert status['law_oc']['configured'] is True


def test_session_settings_are_applied_without_persistence() -> None:
    status = runtime_settings.update_settings(anthropic_api_key='temp-anthropic-key', llm_provider='anthropic', persist=False)

    assert status['anthropic']['configured'] is True
    assert status['anthropic']['source'] == 'memory'
    assert status['anthropic']['saved'] is False
    assert status['llm_provider']['active'] == 'anthropic'
    assert status['llm_provider']['configured'] is True
    assert runtime_settings.get_anthropic_api_key() == 'temp-anthropic-key'
    assert runtime_settings.SETTINGS_PATH.exists() is False


def test_saved_settings_are_persisted_to_file() -> None:
    status = runtime_settings.update_settings(openai_api_key='saved-openai-key', law_oc='saved-law-oc', llm_provider='openai', persist=True)

    assert status['openai']['configured'] is True
    assert status['openai']['source'] == 'file'
    assert status['openai']['saved'] is True
    assert status['law_oc']['configured'] is True
    assert status['llm_provider']['active'] == 'openai'
    assert status['llm_provider']['configured'] is True
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
