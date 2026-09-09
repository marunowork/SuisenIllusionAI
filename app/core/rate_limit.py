"""
Rate Limit 設定

設計書 32章「Rate Limit」に基づき、1 IPあたり 1分間 5リクエストに制限する。
Redisを使用しないため、slowapi(単一プロセス内のインメモリ実装)を利用する。
複数FastAPIインスタンスへスケールする場合は、Nginx側のRate Limitや
共有ストレージ(Redis等)への切り替えを検討する(設計書44章参照)。
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
