"""
画像関連 REST API

設計書 12章(画像生成) / 13章(画像取得) / 14章(画像一覧) / 15章(画像削除) に基づく。

【仕様追加(v0.3)】
- POST /api/v1/images は1回のリクエストで IMAGES_PER_REQUEST 枚(既定5枚)の
  画像URLをまとめて返す。
- クライアントIPアドレス単位で1日あたりの新規生成回数を DAILY_REQUEST_LIMIT_PER_IP
  回(既定2回)に制限する。上限超過時は新規生成を行わず、既存の生成済み画像URLを
  ランダムに返す(ただし UNLIMITED_CLIENT_IPS に該当するIP、既定では
  localhost(127.0.0.1 / ::1)は無制限)。
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query, Request

from app.api.deps import get_image_service
from app.core.config import get_settings
from app.core.rate_limit import limiter
from app.schemas.image import (
    ImageDeleteResponse,
    ImageDetailResponse,
    ImageGenerateRequest,
    ImageGenerateResponse,
    ImageListResponse,
)
from app.services.image_service import ImageService
from app.utils.ip_utils import get_client_ip

router = APIRouter(prefix="/api/v1/images", tags=["images"])

settings = get_settings()


@router.post("", response_model=ImageGenerateResponse, status_code=200)
@limiter.limit(f"{settings.RATE_LIMIT_PER_MINUTE}/minute")
def generate_image(
    request: Request,
    body: ImageGenerateRequest,
    image_service: ImageService = Depends(get_image_service),
) -> ImageGenerateResponse:
    """キーワードからAI画像を同期生成し、Firebaseへ保存する。

    1回のリクエストにつき複数枚(既定5枚)の画像URLを返す。
    また、クライアントIPアドレスの1日あたり新規生成回数が上限を超えている場合は、
    新規生成を行わず既存の生成済み画像URLをランダムに返す
    (localhost等の無制限クライアントを除く)。
    """
    client_ip = get_client_ip(request)
    return image_service.generate_image(body, client_ip)


@router.get("/{image_id}", response_model=ImageDetailResponse)
def get_image(
    image_id: str,
    image_service: ImageService = Depends(get_image_service),
) -> ImageDetailResponse:
    """image_id を指定して画像情報を取得する。"""
    return image_service.get_image(image_id)


@router.get("", response_model=ImageListResponse)
def list_images(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=settings.DEFAULT_PAGE_SIZE, ge=1, le=settings.MAX_PAGE_SIZE),
    keyword: Optional[str] = Query(default=None, max_length=100),
    image_service: ImageService = Depends(get_image_service),
) -> ImageListResponse:
    """画像の一覧をページングで取得する。"""
    return image_service.list_images(page=page, limit=limit, keyword=keyword)


@router.delete("/{image_id}", response_model=ImageDeleteResponse)
def delete_image(
    image_id: str,
    image_service: ImageService = Depends(get_image_service),
) -> ImageDeleteResponse:
    """image_id を指定して画像を物理削除する(Firestore + Storage)。"""
    return image_service.delete_image(image_id)
