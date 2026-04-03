from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response, status

from app.favorites_store import delete_favorite, list_favorites, save_favorite
from app.models import FavoriteSourceInput, FavoriteSourceResponse


router = APIRouter(prefix="/api/favorites", tags=["favorites"])


@router.get("", response_model=list[FavoriteSourceResponse])
def get_favorites() -> list[FavoriteSourceResponse]:
    return [FavoriteSourceResponse.model_validate(item) for item in list_favorites()]


@router.post("", response_model=FavoriteSourceResponse, status_code=status.HTTP_201_CREATED)
def create_favorite(payload: FavoriteSourceInput) -> FavoriteSourceResponse:
    if not any((payload.id, payload.title, payload.reference, payload.detail_link)):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="즐겨찾기할 참조 출처 정보가 부족합니다.")
    favorite = save_favorite(payload)
    return FavoriteSourceResponse.model_validate(favorite)


@router.delete("/{favorite_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_favorite(favorite_id: str) -> Response:
    if not delete_favorite(favorite_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="해당 즐겨찾기를 찾지 못했습니다.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
