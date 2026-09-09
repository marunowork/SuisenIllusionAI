"""
アプリケーション設定

設計書 27章「環境変数」に基づき、.env から設定値を読み込む。
秘密情報（APIキー、サービスアカウント）はここでは値そのものを
ログ出力しないよう注意すること。
"""

from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- アプリケーション ---
    APP_ENV: str = "development"
    APP_NAME: str = "SuisenGalleryAPI Lite"
    LOG_LEVEL: str = "INFO"

    # --- Google Gemini API ---
    GOOGLE_API_KEY: str = ""
    GEMINI_IMAGE_MODEL: str = "gemini-2.5-flash-image"

    # --- Firebase ---
    FIREBASE_PROJECT_ID: str = ""
    FIREBASE_STORAGE_BUCKET: str = ""
    FIREBASE_SERVICE_ACCOUNT_PATH: str = "/app/firebase/service-account.json"
    # Firebase Storage の画像を公開URLにするか(true)、Signed URLにするか(false)
    FIREBASE_PUBLIC_URL: bool = True
    # Signed URL の有効期限(分) FIREBASE_PUBLIC_URL=false の場合に使用
    SIGNED_URL_EXPIRE_MINUTES: int = 60

    # --- 画像処理 ---
    IMAGE_TEMP_DIR: str = "/data/images"
    MAX_IMAGE_SIZE_MB: int = 20
    API_TIMEOUT_SECONDS: int = 300
    # 初期版で許可する image_size / aspect_ratio (設計書 40章)
    ALLOWED_IMAGE_SIZES: List[str] = ["1024"]
    ALLOWED_ASPECT_RATIOS: List[str] = ["1:1", "16:9", "9:16", "4:3", "3:4"]
    # 一時ファイルの掃除対象(時間) 設計書38章
    TEMP_FILE_MAX_AGE_HOURS: int = 24

    # --- Rate Limit (設計書32章、バースト対策) ---
    RATE_LIMIT_PER_MINUTE: int = 5

    # --- 画像生成の追加仕様 ---
    # 1回の生成リクエストで生成する画像枚数
    # 注意: gemini-2.5-flash-image は candidateCount / number_of_images による
    # 複数枚同時生成をサポートしていない(INVALID_ARGUMENTになることを確認済み)。
    # そのため、Gemini APIをこの枚数分ループ呼び出しして実現する。
    IMAGES_PER_REQUEST: int = 5

    # --- IPアドレス単位の1日あたり生成回数制限 ---
    # 1日あたりの「新規生成」を許可する回数(超過分は既存画像をランダムに返す)
    DAILY_REQUEST_LIMIT_PER_IP: int = 2
    # 日次リセットの基準タイムゾーン(時)。9 = JST(UTC+9)
    DAILY_LIMIT_TIMEZONE_OFFSET_HOURS: int = 9
    # 無制限として扱うIPアドレス(ローカル開発・動作確認用)
    UNLIMITED_CLIENT_IPS: List[str] = ["127.0.0.1", "::1", "localhost"]

    # --- ページネーション ---
    DEFAULT_PAGE_SIZE: int = 20
    MAX_PAGE_SIZE: int = 100


@lru_cache
def get_settings() -> Settings:
    return Settings()
