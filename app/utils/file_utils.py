"""
一時ファイル管理ユーティリティ

設計書 19章(Firebase Storage設計) / 38章(一時ファイル管理) に基づく。
"""

from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def build_storage_path(image_id: str, extension: str = "png") -> str:
    """images/YYYY/MM/DD/{image_id}.png 形式のパスを生成する。

    複数枚生成時は、呼び出し側で image_id に連番サフィックスを
    付与した値(例: "{request_id}-0")を渡すこと。
    """
    now = datetime.now(timezone.utc)
    return f"images/{now:%Y}/{now:%m}/{now:%d}/{image_id}.{extension}"


def build_temp_path(temp_dir: str, image_id: str, extension: str = "png") -> str:
    os.makedirs(temp_dir, exist_ok=True)
    return os.path.join(temp_dir, f"{image_id}.{extension}")


def save_temp_file(temp_path: str, data: bytes) -> None:
    with open(temp_path, "wb") as f:
        f.write(data)
    logger.info("temp file saved path=%s size=%d", temp_path, len(data))


def delete_temp_file(temp_path: str) -> None:
    try:
        if os.path.exists(temp_path):
            os.remove(temp_path)
            logger.info("temp file deleted path=%s", temp_path)
    except OSError as exc:
        logger.warning("failed to delete temp file path=%s error=%s", temp_path, exc)


def cleanup_stale_temp_files(temp_dir: str, max_age_hours: int) -> int:
    """異常終了などで残った一時ファイルのうち、
    max_age_hours 以上経過したものを削除する(設計書38章)。
    戻り値は削除件数。
    """
    if not os.path.isdir(temp_dir):
        return 0

    now = time.time()
    max_age_seconds = max_age_hours * 3600
    removed = 0

    for filename in os.listdir(temp_dir):
        file_path = os.path.join(temp_dir, filename)
        if not os.path.isfile(file_path):
            continue
        age = now - os.path.getmtime(file_path)
        if age >= max_age_seconds:
            try:
                os.remove(file_path)
                removed += 1
                logger.info("stale temp file removed path=%s age_hours=%.1f", file_path, age / 3600)
            except OSError as exc:
                logger.warning("failed to remove stale temp file path=%s error=%s", file_path, exc)

    return removed
