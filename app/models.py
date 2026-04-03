from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class DocumentBase(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    category: str = Field(..., min_length=1)
    is_private: bool = True
    title: str = Field(..., min_length=1)
    source: str = Field(..., min_length=1)
    content: str = Field(..., min_length=1)
    practical: str | None = None
    date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    tags: list[str] = Field(default_factory=list)

    @field_validator("tags", mode="before")
    @classmethod
    def normalize_tags(cls, value: Any) -> list[str]:
        if value in (None, ""):
            return []
        if isinstance(value, str):
            return [value]
        return [str(item).strip() for item in value if str(item).strip()]


class DocumentCreate(DocumentBase):
    pass


class DocumentUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    category: str | None = None
    is_private: bool | None = None
    title: str | None = None
    source: str | None = None
    content: str | None = None
    practical: str | None = None
    date: str | None = None
    tags: list[str] | None = None

    @field_validator("tags", mode="before")
    @classmethod
    def normalize_tags(cls, value: Any) -> list[str] | None:
        if value is None:
            return None
        if value == "":
            return []
        if isinstance(value, str):
            return [value]
        return [str(item).strip() for item in value if str(item).strip()]


class DocumentResponse(DocumentBase):
    id: str
    created_at: datetime
    updated_at: datetime


class SearchQuery(BaseModel):
    query: str = Field(..., min_length=1)
    category: str | None = None
    top_k: int = Field(default=5, ge=1, le=50)


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1)
    include_public: bool = True


class ChatResponse(BaseModel):
    answer: str
    sources: list[dict[str, Any]] = Field(default_factory=list)


class FavoriteSourceInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    id: str | None = None
    category: str | None = None
    source_type: str | None = None
    is_private: bool = False
    title: str | None = None
    source: str | None = None
    reference: str | None = None
    citation: str | None = None
    detail_link: str | None = None
    summary: str | None = None
    date: str | None = None


class FavoriteSourceResponse(FavoriteSourceInput):
    favorite_id: str
    created_at: datetime
