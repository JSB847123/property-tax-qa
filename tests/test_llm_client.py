from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import llm_client


@pytest.mark.anyio
async def test_generate_text_dispatches_to_openai(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_openai(system_prompt: str, user_prompt: str, *, max_tokens: int, temperature: float) -> str:
        assert '규칙' in system_prompt
        assert '질문' in user_prompt
        assert max_tokens == 1400
        return 'openai-result'

    monkeypatch.setattr(llm_client, 'get_llm_provider', lambda: 'openai')
    monkeypatch.setattr(llm_client, '_call_openai', fake_openai)

    result = await llm_client.generate_text('규칙', '질문', max_tokens=1400, temperature=0.2)

    assert result == 'openai-result'


@pytest.mark.anyio
async def test_generate_text_dispatches_to_gemini(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_gemini(system_prompt: str, user_prompt: str, *, max_tokens: int, temperature: float) -> str:
        assert max_tokens == 1200
        return 'gemini-result'

    monkeypatch.setattr(llm_client, 'get_llm_provider', lambda: 'gemini')
    monkeypatch.setattr(llm_client, '_call_gemini', fake_gemini)

    result = await llm_client.generate_text('규칙', '질문', max_tokens=1200, temperature=0.1)

    assert result == 'gemini-result'


def test_extract_openai_text_reads_message_output() -> None:
    payload = {
        'output': [
            {
                'type': 'message',
                'content': [
                    {'type': 'output_text', 'text': '첫 번째 문장'},
                    {'type': 'output_text', 'text': '두 번째 문장'},
                ],
            }
        ]
    }

    assert llm_client._extract_openai_text(payload) == '첫 번째 문장\n두 번째 문장'


def test_extract_gemini_text_reads_candidate_parts() -> None:
    payload = {
        'candidates': [
            {
                'content': {
                    'parts': [
                        {'text': 'Gemini 응답 1'},
                        {'text': 'Gemini 응답 2'},
                    ]
                }
            }
        ]
    }

    assert llm_client._extract_gemini_text(payload) == 'Gemini 응답 1\nGemini 응답 2'


def test_extract_glm_text_reads_first_choice_message() -> None:
    payload = {
        'choices': [
            {
                'message': {
                    'content': 'GLM 응답'
                }
            }
        ]
    }

    assert llm_client._extract_glm_text(payload) == 'GLM 응답'
