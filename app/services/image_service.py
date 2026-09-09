"""
ImageService

設計書 10章(画像生成処理) / 48章(FastAPI処理イメージ) /
51章(サービス責務) に基づく。

責務:
- 画像生成処理のオーケストレーション
- 一時ファイル管理
- Firebase保存
- Firestore登録
- IPアドレス単位の1日あたり生成回数制限(仕様追加分)

処理フロー(同期処理、通常時):
  IPアドレスの日次利用回数チェック
      -> (上限内)keyword validation
          -> PromptService (prompt生成)
          -> GeminiService (画像生成 x IMAGES_PER_REQUEST回)
          -> 一時ファイル保存(枚数分)
          -> FirebaseService (Storage upload x枚数分 + Firestore insert)
          -> 一時ファイル削除
          -> 日次利用回数を+1
          -> Response(source="generated")
      -> (上限超過、localhostを除く)
          -> 既存の生成済み画像URLからランダムにIMAGES_PER_REQUEST件選択
          -> Response(source="existing")、新規生成は行わない
"""

from __future__ import annotations

import logging
from typing import List, Optional
from ulid import ULID

from app.core.exceptions import NotFoundError
from app.schemas.image import (
    ImageDeleteResponse,
    ImageDetailResponse,
    ImageGenerateRequest,
    ImageGenerateResponse,
    ImageListItem,
    ImageListResponse,
)
from app.services.firebase_service import FirebaseService
from app.services.gemini_service import GeminiService
from app.services.prompt_service import PromptService
from app.utils.file_utils import (
    build_storage_path,
    build_temp_path,
    delete_temp_file,
    save_temp_file,
)
from app.utils.ip_utils import is_unlimited_client, today_key

logger = logging.getLogger(__name__)


class ImageService:
    def __init__(
        self,
        gemini_service: GeminiService,
        firebase_service: FirebaseService,
        prompt_service: PromptService,
        temp_dir: str,
        images_per_request: int = 5,
        daily_request_limit_per_ip: int = 2,
    ):
        self._gemini_service = gemini_service
        self._firebase_service = firebase_service
        self._prompt_service = prompt_service
        self._temp_dir = temp_dir
        self._images_per_request = images_per_request
        self._daily_request_limit_per_ip = daily_request_limit_per_ip

    # ------------------------------------------------------------------
    # POST /api/v1/images
    # ------------------------------------------------------------------
    def generate_image(
        self, request: ImageGenerateRequest, client_ip: str
    ) -> ImageGenerateResponse:
        unlimited = is_unlimited_client(client_ip)
        date_key = today_key()

        if unlimited:
            daily_used = 0
        else:
            daily_used = self._firebase_service.get_daily_usage(client_ip, date_key)

        logger.info(
            "image request received client_ip=%s unlimited=%s daily_used=%d/%d",
            client_ip,
            unlimited,
            daily_used,
            self._daily_request_limit_per_ip,
        )

        if not unlimited and daily_used >= self._daily_request_limit_per_ip:
            # 1日の新規生成上限に達している -> 既存画像をランダムに返す
            return self._respond_with_existing_images(request, daily_used)

        return self._generate_new_images(request, client_ip, unlimited, daily_used)

    def _respond_with_existing_images(
        self, request: ImageGenerateRequest, daily_used: int
    ) -> ImageGenerateResponse:
        keyword = self._prompt_service.validate_keyword(request.keyword)
        urls = self._firebase_service.get_random_existing_urls(
            self._images_per_request
        )

        logger.info(
            "daily limit exceeded: returning %d existing image(s) instead of generating",
            len(urls),
        )

        return ImageGenerateResponse(
            image_id=None,
            status="completed",
            source="existing",
            keyword=keyword,
            image_urls=urls,
            aspect_ratio=request.aspect_ratio,
            image_size=request.image_size,
            daily_requests_used=daily_used,
            daily_requests_limit=self._daily_request_limit_per_ip,
            is_unlimited_client=False,
        )

    def _generate_new_images(
        self,
        request: ImageGenerateRequest,
        client_ip: str,
        unlimited: bool,
        daily_used: int,
    ) -> ImageGenerateResponse:
        request_id = str(ULID())
        keyword = self._prompt_service.validate_keyword(request.keyword)
        prompt = self._prompt_service.build_prompt(keyword)

        logger.info(
            "image generation started keyword=%s request_id=%s count=%d",
            keyword,
            request_id,
            self._images_per_request,
        )

        created_at = self._firebase_service.now()
        self._firebase_service.create_document(
            request_id,
            {
                "image_id": request_id,
                "keyword": keyword,
                "prompt": prompt,
                "model": self._gemini_service._model,  # noqa: SLF001 - ログ/記録用途
                "status": "processing",
                "image_size": request.image_size,
                "aspect_ratio": request.aspect_ratio,
                "storage_paths": [],
                "image_urls": [],
                "created_at": created_at,
                "completed_at": None,
                "error_code": None,
                "error_message": None,
            },
        )

        temp_paths: List[str] = []
        uploaded_storage_paths: List[str] = []
        image_urls: List[str] = []

        try:
            images_bytes = self._gemini_service.generate_images(
                prompt, self._images_per_request
            )

            for index, image_bytes in enumerate(images_bytes):
                sub_id = f"{request_id}-{index}"
                temp_path = build_temp_path(self._temp_dir, sub_id, "png")
                temp_paths.append(temp_path)
                save_temp_file(temp_path, image_bytes)

                storage_path = build_storage_path(sub_id, "png")
                image_url = self._firebase_service.upload_image(
                    temp_path, storage_path
                )
                uploaded_storage_paths.append(storage_path)
                image_urls.append(image_url)

            completed_at = self._firebase_service.now()
            self._firebase_service.update_document(
                request_id,
                {
                    "status": "completed",
                    "storage_paths": uploaded_storage_paths,
                    "image_urls": image_urls,
                    "completed_at": completed_at,
                },
            )

            if not unlimited:
                self._firebase_service.increment_daily_usage(client_ip, today_key())

            logger.info(
                "image generation completed request_id=%s images=%d",
                request_id,
                len(image_urls),
            )

            return ImageGenerateResponse(
                image_id=request_id,
                status="completed",
                source="generated",
                keyword=keyword,
                image_urls=image_urls,
                aspect_ratio=request.aspect_ratio,
                image_size=request.image_size,
                daily_requests_used=(daily_used if unlimited else daily_used + 1),
                daily_requests_limit=self._daily_request_limit_per_ip,
                is_unlimited_client=unlimited,
            )
        except Exception as exc:
            error_code = getattr(exc, "error_code", "INTERNAL_SERVER_ERROR")
            error_message = getattr(exc, "message", str(exc))
            logger.error(
                "image generation failed request_id=%s error_code=%s",
                request_id,
                error_code,
            )

            # 途中までアップロード済みのStorageオブジェクトはロールバックする
            # (5枚まとめて返す契約のため、部分成功状態を残さない)
            for storage_path in uploaded_storage_paths:
                try:
                    self._firebase_service.delete_storage_object(storage_path)
                except Exception:  # noqa: BLE001 - ロールバック失敗はログのみ
                    logger.warning(
                        "failed to rollback storage object path=%s", storage_path
                    )

            self._firebase_service.update_document(
                request_id,
                {
                    "status": "failed",
                    "error_code": error_code,
                    "error_message": error_message,
                },
            )
            raise
        finally:
            for temp_path in temp_paths:
                delete_temp_file(temp_path)

    # ------------------------------------------------------------------
    # GET /api/v1/images/{image_id}
    # ------------------------------------------------------------------
    def get_image(self, image_id: str) -> ImageDetailResponse:
        doc = self._firebase_service.get_document(image_id)
        if doc is None:
            raise NotFoundError(f"Image not found: {image_id}")
        return ImageDetailResponse(**doc)

    # ------------------------------------------------------------------
    # GET /api/v1/images
    # ------------------------------------------------------------------
    def list_images(
        self, page: int, limit: int, keyword: Optional[str] = None
    ) -> ImageListResponse:
        docs, total = self._firebase_service.list_documents(page, limit, keyword)
        items = [
            ImageListItem(
                image_id=doc["image_id"],
                keyword=doc["keyword"],
                status=doc["status"],
                image_urls=doc.get("image_urls") or [],
                created_at=doc.get("created_at"),
            )
            for doc in docs
        ]
        return ImageListResponse(items=items, page=page, limit=limit, total=total)

    # ------------------------------------------------------------------
    # DELETE /api/v1/images/{image_id}
    # ------------------------------------------------------------------
    def delete_image(self, image_id: str) -> ImageDeleteResponse:
        doc = self._firebase_service.get_document(image_id)
        if doc is None:
            raise NotFoundError(f"Image not found: {image_id}")

        storage_paths = doc.get("storage_paths") or []
        for storage_path in storage_paths:
            self._firebase_service.delete_storage_object(storage_path)
        self._firebase_service.delete_document(image_id)

        logger.info("image deleted image_id=%s (removed %d file(s))", image_id, len(storage_paths))
        return ImageDeleteResponse(image_id=image_id, status="deleted")
