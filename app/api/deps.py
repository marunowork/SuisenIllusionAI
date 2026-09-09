"""
FastAPI Dependency Injection

各サービスをシングルトンとして提供する。
"""

from functools import lru_cache

from app.core.config import get_settings
from app.services.firebase_service import FirebaseService
from app.services.gemini_service import GeminiService
from app.services.image_service import ImageService
from app.services.prompt_service import PromptService


@lru_cache
def get_prompt_service() -> PromptService:
    return PromptService()


@lru_cache
def get_gemini_service() -> GeminiService:
    settings = get_settings()
    return GeminiService(
        api_key=settings.GOOGLE_API_KEY,
        model=settings.GEMINI_IMAGE_MODEL,
        timeout_seconds=settings.API_TIMEOUT_SECONDS,
    )


@lru_cache
def get_firebase_service() -> FirebaseService:
    settings = get_settings()
    return FirebaseService(
        service_account_path=settings.FIREBASE_SERVICE_ACCOUNT_PATH,
        storage_bucket=settings.FIREBASE_STORAGE_BUCKET,
        public_url=settings.FIREBASE_PUBLIC_URL,
        signed_url_expire_minutes=settings.SIGNED_URL_EXPIRE_MINUTES,
    )


@lru_cache
def get_image_service() -> ImageService:
    settings = get_settings()
    return ImageService(
        gemini_service=get_gemini_service(),
        firebase_service=get_firebase_service(),
        prompt_service=get_prompt_service(),
        temp_dir=settings.IMAGE_TEMP_DIR,
        images_per_request=settings.IMAGES_PER_REQUEST,
        daily_request_limit_per_ip=settings.DAILY_REQUEST_LIMIT_PER_IP,
    )
