"""
クライアントIPアドレス関連ユーティリティ

IPアドレス単位の1日あたり生成回数制限(仕様追加分)のために、
リクエスト元IPの取得・ローカル判定・日付キーの算出を行う。

注意:
- 本APIはNginxの背後で稼働する前提(docker-compose.yml参照)。
  nginx/nginx.conf で X-Forwarded-For / X-Real-IP を設定済みのため、
  それらのヘッダーを優先してクライアントの実IPを取得する。
- Nginxを経由しない直接アクセス(ローカル開発時にuvicornへ直接curl等)の場合は
  request.client.host (通常 127.0.0.1) を使用する。
- ヘッダーは経路上で偽装され得るため、本APIを直接インターネットに公開する
  構成(Nginx以外からの直接アクセスを許す構成)にする場合は、
  信頼できるリバースプロキシのみがこのヘッダーを設定できることを
  别途保証すること。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import Request

from app.core.config import get_settings

_settings = get_settings()


def get_client_ip(request: Request) -> str:
    """クライアントの実IPアドレスを取得する。"""
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        # "client, proxy1, proxy2" の形式なので先頭(最も元のクライアント)を採用する
        return forwarded_for.split(",")[0].strip()

    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()

    if request.client and request.client.host:
        return request.client.host

    return "unknown"


def is_unlimited_client(ip: str) -> bool:
    """ローカル開発・動作確認用の無制限クライアントかどうかを判定する。"""
    return ip in _settings.UNLIMITED_CLIENT_IPS


def today_key() -> str:
    """日次リセットの基準タイムゾーンにおける今日の日付キー(YYYY-MM-DD)を返す。"""
    tz = timezone(timedelta(hours=_settings.DAILY_LIMIT_TIMEZONE_OFFSET_HOURS))
    return datetime.now(tz).strftime("%Y-%m-%d")
