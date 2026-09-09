"""
SuisenGalleryAPI Lite

AI画像生成Web API 簡易版のエントリポイント。

設計書「AI画像生成Web API 簡易版 詳細設計書」に基づく実装。
Redis / Celery / Worker / Frontend は使用せず、
FastAPIから Gemini API / Firebase Storage / Firestore を
同期的に呼び出すシンプルな構成とする。
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from app.api.v1 import health, images
from app.core.config import get_settings
from app.core.exceptions import AppError
from app.core.logging_config import setup_logging
from app.core.rate_limit import limiter
from app.utils.file_utils import cleanup_stale_temp_files

setup_logging()
logger = logging.getLogger(__name__)

settings = get_settings()

app = FastAPI(
    title=settings.APP_NAME,
    version="0.1.0",
    description="キーワードからAI画像を生成し、Firebase Storage / Firestoreへ保存するREST API",
)

app.state.limiter = limiter
app.include_router(health.router)
app.include_router(images.router)


# ---------------------------------------------------------------------------
# 例外ハンドラ (設計書34, 35章)
# ---------------------------------------------------------------------------
@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error_code": exc.error_code, "message": exc.message},
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    logger.warning("request validation error: %s", exc.errors())
    return JSONResponse(
        status_code=400,
        content={
            "error_code": "INVALID_REQUEST",
            "message": "Invalid request parameters.",
        },
    )


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    logger.warning("rate limit exceeded ip=%s", request.client.host if request.client else "unknown")
    return JSONResponse(
        status_code=429,
        content={
            "error_code": "RATE_LIMIT_EXCEEDED",
            "message": "Too many requests. Please try again later.",
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error("unhandled exception: %s", type(exc).__name__, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error_code": "INTERNAL_SERVER_ERROR",
            "message": "Internal server error.",
        },
    )


# ---------------------------------------------------------------------------
# 起動時処理
# ---------------------------------------------------------------------------
@app.on_event("startup")
async def on_startup() -> None:
    logger.info("%s starting up (env=%s)", settings.APP_NAME, settings.APP_ENV)
    # 異常終了で残った一時ファイルを起動時にも掃除しておく(設計書38章)
    removed = cleanup_stale_temp_files(
        settings.IMAGE_TEMP_DIR, settings.TEMP_FILE_MAX_AGE_HOURS
    )
    if removed:
        logger.info("cleaned up %d stale temp files on startup", removed)


@app.on_event("shutdown")
async def on_shutdown() -> None:
    logger.info("%s shutting down", settings.APP_NAME)
