"""
ログ設定 (設計書 41章)

INFO / WARNING / ERROR を出力する。
APIキーなど秘密情報は絶対にログへ出力しない。
"""

import logging
import sys

from app.core.config import get_settings


def setup_logging() -> None:
    settings = get_settings()

    level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    # 重複ハンドラ防止
    root_logger.handlers.clear()
    root_logger.addHandler(handler)

    # 過度なアクセスログを抑制(必要に応じて調整)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
