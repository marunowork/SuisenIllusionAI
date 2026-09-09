"""
アプリケーション例外定義

設計書 34章「エラー設計」/ 35章「エラーレスポンス」に基づく。

error_code                    | HTTP
-------------------------------|------
INVALID_REQUEST                | 400
IMAGE_GENERATION_API_ERROR     | 502
IMAGE_GENERATION_TIMEOUT       | 504
FIREBASE_UPLOAD_ERROR          | 502
NOT_FOUND                      | 404
RATE_LIMIT_EXCEEDED            | 429
INTERNAL_SERVER_ERROR          | 500
"""

from __future__ import annotations


class AppError(Exception):
    """アプリケーション共通の基底例外"""

    error_code: str = "INTERNAL_SERVER_ERROR"
    status_code: int = 500
    default_message: str = "Internal server error."

    def __init__(self, message: str | None = None):
        self.message = message or self.default_message
        super().__init__(self.message)


class InvalidRequestError(AppError):
    error_code = "INVALID_REQUEST"
    status_code = 400
    default_message = "Invalid request."


class NotFoundError(AppError):
    error_code = "NOT_FOUND"
    status_code = 404
    default_message = "Resource not found."


class ImageGenerationAPIError(AppError):
    error_code = "IMAGE_GENERATION_API_ERROR"
    status_code = 502
    default_message = "Image generation failed."


class ImageGenerationTimeoutError(AppError):
    error_code = "IMAGE_GENERATION_TIMEOUT"
    status_code = 504
    default_message = "Image generation timed out."


class FirebaseUploadError(AppError):
    error_code = "FIREBASE_UPLOAD_ERROR"
    status_code = 502
    default_message = "Failed to upload image to Firebase Storage."


class FirestoreError(AppError):
    error_code = "FIRESTORE_ERROR"
    status_code = 502
    default_message = "Failed to access Firestore."


class RateLimitExceededError(AppError):
    error_code = "RATE_LIMIT_EXCEEDED"
    status_code = 429
    default_message = "Too many requests. Please try again later."


class InternalServerError(AppError):
    error_code = "INTERNAL_SERVER_ERROR"
    status_code = 500
    default_message = "Internal server error."
