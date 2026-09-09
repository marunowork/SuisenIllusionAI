"""
Pydantic スキーマ定義

設計書 12章(画像生成API)、13章(画像取得API)、14章(画像一覧API)、
15章(画像削除API)、49章/50章(Pydantic Request/Response) に基づく。

【仕様追加(v0.3)】
- 1回の生成リクエストにつき images.py の IMAGES_PER_REQUEST 枚(既定5枚)の
  画像URLをまとめて返す(image_url: str -> image_urls: List[str] に変更)。
- IPアドレス単位の1日あたり生成回数制限を導入。上限超過時は新規生成を行わず、
  既存の生成済み画像URLをランダムに返す(この場合 source="existing")。
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from app.core.config import get_settings

_settings = get_settings()


# ---------------------------------------------------------------------------
# 画像生成 (POST /api/v1/images)
# ---------------------------------------------------------------------------
class ImageGenerateRequest(BaseModel):
    keyword: str = Field(min_length=1, max_length=100)
    aspect_ratio: str = Field(default="16:9")
    image_size: str = Field(default="1024")

    @field_validator("keyword")
    @classmethod
    def validate_keyword(cls, v: str) -> str:
        # 制御文字の禁止 (設計書31章)
        if any(ord(ch) < 0x20 or ord(ch) == 0x7F for ch in v):
            raise ValueError("keyword contains control characters.")
        normalized = v.strip()
        if not normalized:
            raise ValueError("keyword must not be empty.")
        return normalized

    @field_validator("aspect_ratio")
    @classmethod
    def validate_aspect_ratio(cls, v: str) -> str:
        if v not in _settings.ALLOWED_ASPECT_RATIOS:
            raise ValueError(
                f"aspect_ratio must be one of {_settings.ALLOWED_ASPECT_RATIOS}."
            )
        return v

    @field_validator("image_size")
    @classmethod
    def validate_image_size(cls, v: str) -> str:
        if v not in _settings.ALLOWED_IMAGE_SIZES:
            raise ValueError(
                f"image_size must be one of {_settings.ALLOWED_IMAGE_SIZES}."
            )
        return v


class ImageGenerateResponse(BaseModel):
    image_id: Optional[str] = None
    status: str
    # "generated": 新規生成 / "existing": 1日の生成上限超過により既存画像を返却
    source: str
    keyword: str
    image_urls: List[str]
    aspect_ratio: str
    image_size: str
    # 呼び出し元IPの当日時点の「新規生成」利用回数(このリクエスト分を含む)
    daily_requests_used: int
    daily_requests_limit: int
    # localhost等、日次上限の対象外クライアントかどうか
    is_unlimited_client: bool = False


# ---------------------------------------------------------------------------
# 画像取得 (GET /api/v1/images/{image_id})
# ---------------------------------------------------------------------------
class ImageDetailResponse(BaseModel):
    image_id: str
    status: str
    keyword: str
    prompt: Optional[str] = None
    image_urls: List[str] = []
    aspect_ratio: Optional[str] = None
    image_size: Optional[str] = None
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None


# ---------------------------------------------------------------------------
# 画像一覧 (GET /api/v1/images)
# ---------------------------------------------------------------------------
class ImageListItem(BaseModel):
    image_id: str
    keyword: str
    status: str
    image_urls: List[str] = []
    created_at: Optional[datetime] = None


class ImageListResponse(BaseModel):
    items: List[ImageListItem]
    page: int
    limit: int
    total: int


# ---------------------------------------------------------------------------
# 画像削除 (DELETE /api/v1/images/{image_id})
# ---------------------------------------------------------------------------
class ImageDeleteResponse(BaseModel):
    image_id: str
    status: str = "deleted"


# ---------------------------------------------------------------------------
# エラーレスポンス (設計書35章)
# ---------------------------------------------------------------------------
class ErrorResponse(BaseModel):
    error_code: str
    message: str


# ---------------------------------------------------------------------------
# Health Check (設計書16章)
# ---------------------------------------------------------------------------
class HealthResponse(BaseModel):
    status: str = "ok"
