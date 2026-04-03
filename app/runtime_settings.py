from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from threading import Lock
from typing import Literal

from dotenv import load_dotenv

from app.database import DATA_DIR


logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parents[1]
ENV_PATH = BASE_DIR / '.env'
SETTINGS_PATH = DATA_DIR / 'runtime_settings.json'
LLM_PROVIDERS = ('anthropic', 'openai', 'gemini', 'glm')
PROVIDER_KEY_MAP = {
    'anthropic': 'ANTHROPIC_API_KEY',
    'openai': 'OPENAI_API_KEY',
    'gemini': 'GEMINI_API_KEY',
    'glm': 'GLM_API_KEY',
}
SUPPORTED_KEYS = (*PROVIDER_KEY_MAP.values(), 'LAW_OC', 'LLM_PROVIDER')
SOURCE_TYPE = Literal['memory', 'file', 'env', 'missing']

_lock = Lock()
_runtime_overrides: dict[str, str] = {}


def _ensure_settings_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _normalize_value(value: str | None) -> str:
    return (value or '').strip()


def _normalize_provider(value: str | None) -> str:
    normalized = _normalize_value(value).lower()
    return normalized if normalized in LLM_PROVIDERS else ''


def _load_persisted_settings() -> dict[str, str]:
    _ensure_settings_dir()
    if not SETTINGS_PATH.exists():
        return {}

    try:
        raw = json.loads(SETTINGS_PATH.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        logger.exception('Failed to read persisted runtime settings from %s', SETTINGS_PATH)
        return {}

    if not isinstance(raw, dict):
        return {}

    data: dict[str, str] = {}
    for key in SUPPORTED_KEYS:
        value = _normalize_provider(raw.get(key)) if key == 'LLM_PROVIDER' else _normalize_value(raw.get(key))
        if value:
            data[key] = value
    return data


def _write_persisted_settings(data: dict[str, str]) -> None:
    _ensure_settings_dir()
    SETTINGS_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def _get_env_value(name: str) -> str:
    load_dotenv(ENV_PATH)
    raw = os.getenv(name, '')
    return _normalize_provider(raw) if name == 'LLM_PROVIDER' else _normalize_value(raw)


def get_config_value(name: str) -> str:
    if name not in SUPPORTED_KEYS:
        raise KeyError(f'Unsupported runtime setting: {name}')

    with _lock:
        runtime_value = _runtime_overrides.get(name, '')
    if runtime_value:
        return runtime_value

    persisted = _load_persisted_settings().get(name, '')
    if persisted:
        return persisted

    return _get_env_value(name)


def _resolve_source(name: str) -> SOURCE_TYPE:
    with _lock:
        if _runtime_overrides.get(name, ''):
            return 'memory'

    persisted = _load_persisted_settings().get(name, '')
    if persisted:
        return 'file'

    if _get_env_value(name):
        return 'env'
    return 'missing'


def _setting_status(name: str, persisted: dict[str, str]) -> dict[str, str | bool]:
    return {
        'configured': bool(get_config_value(name)),
        'source': _resolve_source(name),
        'saved': bool(persisted.get(name)),
    }


def get_llm_provider() -> str:
    selected = _normalize_provider(get_config_value('LLM_PROVIDER'))
    if selected:
        return selected

    for provider, key_name in PROVIDER_KEY_MAP.items():
        if get_config_value(key_name):
            return provider
    return 'anthropic'


def get_settings_status() -> dict[str, object]:
    persisted = _load_persisted_settings()
    explicit_provider = _normalize_provider(get_config_value('LLM_PROVIDER'))

    return {
        'llm_provider': {
            'active': get_llm_provider(),
            'selected': explicit_provider or None,
            'source': _resolve_source('LLM_PROVIDER'),
            'saved': bool(persisted.get('LLM_PROVIDER')),
        },
        'anthropic': _setting_status('ANTHROPIC_API_KEY', persisted),
        'openai': _setting_status('OPENAI_API_KEY', persisted),
        'gemini': _setting_status('GEMINI_API_KEY', persisted),
        'glm': _setting_status('GLM_API_KEY', persisted),
        'law_oc': _setting_status('LAW_OC', persisted),
        'settings_path': str(SETTINGS_PATH),
    }


def update_settings(
    *,
    anthropic_api_key: str | None = None,
    openai_api_key: str | None = None,
    gemini_api_key: str | None = None,
    glm_api_key: str | None = None,
    law_oc: str | None = None,
    llm_provider: str | None = None,
    persist: bool = False,
) -> dict[str, object]:
    updates = {
        'ANTHROPIC_API_KEY': _normalize_value(anthropic_api_key),
        'OPENAI_API_KEY': _normalize_value(openai_api_key),
        'GEMINI_API_KEY': _normalize_value(gemini_api_key),
        'GLM_API_KEY': _normalize_value(glm_api_key),
        'LAW_OC': _normalize_value(law_oc),
    }

    normalized_provider = _normalize_provider(llm_provider)
    if llm_provider is not None and not normalized_provider:
        raise ValueError('지원하지 않는 답변 제공자입니다.')
    if normalized_provider:
        updates['LLM_PROVIDER'] = normalized_provider

    filtered_updates = {key: value for key, value in updates.items() if value}
    if not filtered_updates:
        raise ValueError('적용할 설정값이 없습니다.')

    with _lock:
        if persist:
            persisted = _load_persisted_settings()
            persisted.update(filtered_updates)
            _write_persisted_settings(persisted)
            for key in filtered_updates:
                _runtime_overrides.pop(key, None)
        else:
            _runtime_overrides.update(filtered_updates)

    return get_settings_status()


def clear_runtime_overrides() -> dict[str, object]:
    with _lock:
        _runtime_overrides.clear()
    return get_settings_status()


def get_provider_api_key(provider: str) -> str:
    key_name = PROVIDER_KEY_MAP.get(provider)
    if not key_name:
        raise KeyError(f'Unsupported provider: {provider}')
    return get_config_value(key_name)


def get_anthropic_api_key() -> str:
    return get_config_value('ANTHROPIC_API_KEY')


def get_openai_api_key() -> str:
    return get_config_value('OPENAI_API_KEY')


def get_gemini_api_key() -> str:
    return get_config_value('GEMINI_API_KEY')


def get_glm_api_key() -> str:
    return get_config_value('GLM_API_KEY')


def get_law_oc() -> str:
    return get_config_value('LAW_OC')
