from __future__ import annotations

import logging
from typing import Any, Literal

import httpx

try:
    from anthropic import AsyncAnthropic
except ImportError:  # pragma: no cover - dependency may not be installed yet
    AsyncAnthropic = None  # type: ignore[assignment]

from app.runtime_settings import get_llm_provider, get_provider_api_key


logger = logging.getLogger(__name__)

LLMProvider = Literal['anthropic', 'openai', 'gemini', 'glm']
REQUEST_TIMEOUT = 60.0
DEFAULT_MODELS: dict[str, str] = {
    'anthropic': 'claude-sonnet-4-20250514',
    'openai': 'gpt-5.4-mini',
    'gemini': 'gemini-2.5-flash',
    'glm': 'glm-5',
}
PROVIDER_LABELS = {
    'anthropic': 'Anthropic Claude',
    'openai': 'OpenAI',
    'gemini': 'Google Gemini',
    'glm': 'Zhipu GLM',
}
OPENAI_RESPONSES_URL = 'https://api.openai.com/v1/responses'
GEMINI_URL_TEMPLATE = 'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent'
GLM_CHAT_COMPLETIONS_URL = 'https://open.bigmodel.cn/api/paas/v4/chat/completions'


class LLMClientError(Exception):
    """Raised when the configured LLM provider cannot generate a response."""


async def generate_text(system_prompt: str, user_prompt: str, *, max_tokens: int, temperature: float) -> str:
    provider = get_llm_provider()
    if provider == 'anthropic':
        return await _call_anthropic(system_prompt, user_prompt, max_tokens=max_tokens, temperature=temperature)
    if provider == 'openai':
        return await _call_openai(system_prompt, user_prompt, max_tokens=max_tokens, temperature=temperature)
    if provider == 'gemini':
        return await _call_gemini(system_prompt, user_prompt, max_tokens=max_tokens, temperature=temperature)
    if provider == 'glm':
        return await _call_glm(system_prompt, user_prompt, max_tokens=max_tokens, temperature=temperature)
    raise LLMClientError('지원하지 않는 답변 제공자입니다.')


async def _call_anthropic(system_prompt: str, user_prompt: str, *, max_tokens: int, temperature: float) -> str:
    api_key = get_provider_api_key('anthropic')
    if not api_key:
        raise LLMClientError('ANTHROPIC_API_KEY가 설정되어 있지 않습니다.')
    if AsyncAnthropic is None:
        raise LLMClientError('anthropic 패키지가 설치되어 있지 않습니다. requirements.txt 의존성을 먼저 설치하세요.')

    try:
        async with AsyncAnthropic(api_key=api_key) as client:
            message = await client.messages.create(
                model=DEFAULT_MODELS['anthropic'],
                max_tokens=max_tokens,
                temperature=temperature,
                system=system_prompt,
                messages=[{'role': 'user', 'content': user_prompt}],
            )
    except Exception as exc:  # pragma: no cover - depends on external API
        logger.exception('Anthropic API call failed: %s', exc)
        raise LLMClientError('Anthropic API 호출에 실패했습니다.') from exc

    parts = [getattr(block, 'text', '') for block in getattr(message, 'content', []) if getattr(block, 'type', None) == 'text']
    answer = '\n'.join(part.strip() for part in parts if part and part.strip()).strip()
    if not answer:
        raise LLMClientError('Anthropic 응답에서 텍스트를 추출하지 못했습니다.')
    return answer


async def _call_openai(system_prompt: str, user_prompt: str, *, max_tokens: int, temperature: float) -> str:
    api_key = get_provider_api_key('openai')
    if not api_key:
        raise LLMClientError('OPENAI_API_KEY가 설정되어 있지 않습니다.')

    payload = {
        'model': DEFAULT_MODELS['openai'],
        'input': [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': user_prompt},
        ],
        'max_output_tokens': max_tokens,
        'temperature': temperature,
    }
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json',
    }

    data = await _post_json(OPENAI_RESPONSES_URL, headers=headers, payload=payload, provider='openai')
    answer = _extract_openai_text(data)
    if not answer:
        raise LLMClientError('OpenAI 응답에서 텍스트를 추출하지 못했습니다.')
    return answer


async def _call_gemini(system_prompt: str, user_prompt: str, *, max_tokens: int, temperature: float) -> str:
    api_key = get_provider_api_key('gemini')
    if not api_key:
        raise LLMClientError('GEMINI_API_KEY가 설정되어 있지 않습니다.')

    payload = {
        'systemInstruction': {
            'parts': [{'text': system_prompt}],
        },
        'contents': [
            {
                'role': 'user',
                'parts': [{'text': user_prompt}],
            }
        ],
        'generationConfig': {
            'temperature': temperature,
            'maxOutputTokens': max_tokens,
        },
    }
    headers = {
        'x-goog-api-key': api_key,
        'Content-Type': 'application/json',
    }

    data = await _post_json(GEMINI_URL_TEMPLATE.format(model=DEFAULT_MODELS['gemini']), headers=headers, payload=payload, provider='gemini')
    answer = _extract_gemini_text(data)
    if not answer:
        raise LLMClientError('Gemini 응답에서 텍스트를 추출하지 못했습니다.')
    return answer


async def _call_glm(system_prompt: str, user_prompt: str, *, max_tokens: int, temperature: float) -> str:
    api_key = get_provider_api_key('glm')
    if not api_key:
        raise LLMClientError('GLM_API_KEY가 설정되어 있지 않습니다.')

    payload = {
        'model': DEFAULT_MODELS['glm'],
        'messages': [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': user_prompt},
        ],
        'max_tokens': max_tokens,
        'temperature': temperature,
    }
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json',
    }

    data = await _post_json(GLM_CHAT_COMPLETIONS_URL, headers=headers, payload=payload, provider='glm')
    answer = _extract_glm_text(data)
    if not answer:
        raise LLMClientError('GLM 응답에서 텍스트를 추출하지 못했습니다.')
    return answer


async def _post_json(url: str, *, headers: dict[str, str], payload: dict[str, Any], provider: LLMProvider) -> dict[str, Any]:
    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT, follow_redirects=True) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPStatusError as exc:  # pragma: no cover - depends on external API
        detail = exc.response.text.strip()
        logger.exception('%s API returned an error: %s', PROVIDER_LABELS[provider], detail or exc)
        raise LLMClientError(f'{PROVIDER_LABELS[provider]} API 호출에 실패했습니다.') from exc
    except Exception as exc:  # pragma: no cover - depends on external API
        logger.exception('%s API call failed: %s', PROVIDER_LABELS[provider], exc)
        raise LLMClientError(f'{PROVIDER_LABELS[provider]} API 호출에 실패했습니다.') from exc

    if not isinstance(data, dict):
        raise LLMClientError(f'{PROVIDER_LABELS[provider]} 응답 형식이 올바르지 않습니다.')
    return data


def _extract_openai_text(data: dict[str, Any]) -> str:
    output_text = data.get('output_text')
    if isinstance(output_text, str) and output_text.strip():
        return output_text.strip()

    parts: list[str] = []
    for item in data.get('output', []):
        if not isinstance(item, dict) or item.get('type') != 'message':
            continue
        for content in item.get('content', []):
            if not isinstance(content, dict):
                continue
            text = content.get('text') or content.get('value')
            if isinstance(text, str) and text.strip():
                parts.append(text.strip())
    return '\n'.join(parts).strip()


def _extract_gemini_text(data: dict[str, Any]) -> str:
    parts: list[str] = []
    for candidate in data.get('candidates', []):
        if not isinstance(candidate, dict):
            continue
        content = candidate.get('content') or {}
        for part in content.get('parts', []):
            if not isinstance(part, dict):
                continue
            text = part.get('text')
            if isinstance(text, str) and text.strip():
                parts.append(text.strip())
    return '\n'.join(parts).strip()


def _extract_glm_text(data: dict[str, Any]) -> str:
    choices = data.get('choices') or []
    if not choices:
        return ''

    message = choices[0].get('message') if isinstance(choices[0], dict) else None
    if not isinstance(message, dict):
        return ''

    content = message.get('content')
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = [str(part).strip() for part in content if str(part).strip()]
        return '\n'.join(parts).strip()
    return ''
