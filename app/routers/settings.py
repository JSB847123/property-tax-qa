from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from app.runtime_settings import clear_runtime_overrides, get_settings_status, update_settings


router = APIRouter(prefix='/api/settings', tags=['settings'])


class CredentialUpdateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    anthropic_api_key: str | None = Field(default=None)
    openai_api_key: str | None = Field(default=None)
    gemini_api_key: str | None = Field(default=None)
    glm_api_key: str | None = Field(default=None)
    law_oc: str | None = Field(default=None)
    llm_provider: Literal['anthropic', 'openai', 'gemini', 'glm'] | None = Field(default=None)
    mode: Literal['session', 'saved'] = Field(default='session')


@router.get('')
def get_runtime_settings() -> dict[str, object]:
    return get_settings_status()


@router.post('/credentials')
def update_runtime_settings(payload: CredentialUpdateRequest) -> dict[str, object]:
    try:
        settings = update_settings(
            anthropic_api_key=payload.anthropic_api_key,
            openai_api_key=payload.openai_api_key,
            gemini_api_key=payload.gemini_api_key,
            glm_api_key=payload.glm_api_key,
            law_oc=payload.law_oc,
            llm_provider=payload.llm_provider,
            persist=payload.mode == 'saved',
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return {
        'message': '설정이 저장되었습니다.' if payload.mode == 'saved' else '이번 실행에만 설정이 적용되었습니다.',
        'mode': payload.mode,
        'settings': settings,
    }


@router.delete('/session')
def reset_session_settings() -> dict[str, object]:
    return {
        'message': '임시 설정이 초기화되었습니다.',
        'settings': clear_runtime_overrides(),
    }
