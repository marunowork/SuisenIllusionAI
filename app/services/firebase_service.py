"""
FirebaseService

設計書 17章(Firestore設計) / 19章(Firebase Storage設計) /
20章(Firebaseアクセス方式) / 51章(サービス責務) に基づく。

責務:
- Storage upload / delete
- Firestore insert / find / delete (+ update)

Firebase Admin SDK を使用し、クライアントから直接Storageへ
アップロードする方式は採らない。
"""

from __future__ import annotations

import logging
import os
import random
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import firebase_admin
from firebase_admin import credentials, firestore, storage
from google.cloud.firestore_v1 import FieldFilter
from google.cloud.exceptions import GoogleCloudError

from app.core.exceptions import FirebaseUploadError, FirestoreError

logger = logging.getLogger(__name__)

_COLLECTION = "images"
_IP_USAGE_COLLECTION = "ip_usage"


class FirebaseService:
    def __init__(
        self,
        service_account_path: str,
        storage_bucket: str,
        public_url: bool = True,
        signed_url_expire_minutes: int = 60,
    ):
        self._public_url = public_url
        self._signed_url_expire_minutes = signed_url_expire_minutes

        if not firebase_admin._apps:
            if not os.path.exists(service_account_path):
                logger.warning(
                    "Firebase service account file not found at %s. "
                    "Firebase calls will fail until it is provided.",
                    service_account_path,
                )
                cred = None
            else:
                cred = credentials.Certificate(service_account_path)

            if cred is not None:
                firebase_admin.initialize_app(
                    cred, {"storageBucket": storage_bucket}
                )

        self._db = firestore.client() if firebase_admin._apps else None
        self._bucket = storage.bucket() if firebase_admin._apps else None

    def _ensure_initialized(self) -> None:
        if self._db is None or self._bucket is None:
            raise FirestoreError(
                "Firebase is not initialized. Check FIREBASE_SERVICE_ACCOUNT_PATH "
                "and FIREBASE_STORAGE_BUCKET settings."
            )

    # ------------------------------------------------------------------
    # Storage
    # ------------------------------------------------------------------
    def upload_image(self, local_path: str, storage_path: str) -> str:
        """ローカルの一時ファイルをFirebase Storageへアップロードし、
        画像を取得するためのURLを返す。
        """
        self._ensure_initialized()
        try:
            blob = self._bucket.blob(storage_path)
            blob.upload_from_filename(local_path)

            if self._public_url:
                blob.make_public()
                url = blob.public_url
            else:
                url = blob.generate_signed_url(
                    expiration=self._signed_url_expire_minutes * 60
                )
            logger.info("firebase upload completed path=%s", storage_path)
            return url
        except GoogleCloudError as exc:
            logger.error("firebase upload failed: %s", type(exc).__name__)
            raise FirebaseUploadError() from exc
        except Exception as exc:  # noqa: BLE001
            logger.error("firebase upload unexpected error: %s", type(exc).__name__)
            raise FirebaseUploadError() from exc

    def delete_storage_object(self, storage_path: str) -> None:
        self._ensure_initialized()
        try:
            blob = self._bucket.blob(storage_path)
            if blob.exists():
                blob.delete()
                logger.info("firebase storage object deleted path=%s", storage_path)
        except GoogleCloudError as exc:
            logger.error("firebase delete failed: %s", type(exc).__name__)
            raise FirebaseUploadError("Failed to delete image from Firebase Storage.") from exc

    # ------------------------------------------------------------------
    # Firestore
    # ------------------------------------------------------------------
    def create_document(self, image_id: str, data: Dict[str, Any]) -> None:
        self._ensure_initialized()
        try:
            self._db.collection(_COLLECTION).document(image_id).set(data)
        except GoogleCloudError as exc:
            logger.error("firestore create failed: %s", type(exc).__name__)
            raise FirestoreError() from exc

    def update_document(self, image_id: str, data: Dict[str, Any]) -> None:
        self._ensure_initialized()
        try:
            self._db.collection(_COLLECTION).document(image_id).update(data)
        except GoogleCloudError as exc:
            logger.error("firestore update failed: %s", type(exc).__name__)
            raise FirestoreError() from exc

    def get_document(self, image_id: str) -> Optional[Dict[str, Any]]:
        self._ensure_initialized()
        try:
            doc = self._db.collection(_COLLECTION).document(image_id).get()
            return doc.to_dict() if doc.exists else None
        except GoogleCloudError as exc:
            logger.error("firestore get failed: %s", type(exc).__name__)
            raise FirestoreError() from exc

    def delete_document(self, image_id: str) -> None:
        self._ensure_initialized()
        try:
            self._db.collection(_COLLECTION).document(image_id).delete()
        except GoogleCloudError as exc:
            logger.error("firestore delete failed: %s", type(exc).__name__)
            raise FirestoreError() from exc

    def list_documents(
        self, page: int, limit: int, keyword: Optional[str] = None
    ) -> Tuple[List[Dict[str, Any]], int]:
        """一覧取得。初期版のシンプルな実装として、
        条件に合う全件を作成日時降順で取得し、Python側でページングする。
        """
        self._ensure_initialized()
        try:
            query = self._db.collection(_COLLECTION)
            if keyword:
                query = query.where(filter=FieldFilter("keyword", "==", keyword))
            query = query.order_by("created_at", direction=firestore.Query.DESCENDING)

            docs = [doc.to_dict() for doc in query.stream()]
            total = len(docs)

            start = (page - 1) * limit
            end = start + limit
            items = docs[start:end]
            return items, total
        except GoogleCloudError as exc:
            logger.error("firestore list failed: %s", type(exc).__name__)
            raise FirestoreError() from exc

    # ------------------------------------------------------------------
    # IPアドレス単位の1日あたり生成回数管理(仕様追加分)
    # ------------------------------------------------------------------
    def get_daily_usage(self, client_ip: str, date_key: str) -> int:
        """指定IP・指定日付キーにおける「新規生成」回数を取得する。"""
        self._ensure_initialized()
        try:
            doc_id = f"{client_ip}_{date_key}"
            doc = self._db.collection(_IP_USAGE_COLLECTION).document(doc_id).get()
            if not doc.exists:
                return 0
            return int(doc.to_dict().get("count", 0))
        except GoogleCloudError as exc:
            logger.error("firestore get_daily_usage failed: %s", type(exc).__name__)
            raise FirestoreError() from exc

    def increment_daily_usage(self, client_ip: str, date_key: str) -> None:
        """指定IP・指定日付キーの「新規生成」回数を1増やす。

        ドキュメントが存在しない場合は作成する(merge=True)。
        firestore.Increment によりサーバー側でアトミックに加算される。
        """
        self._ensure_initialized()
        try:
            doc_id = f"{client_ip}_{date_key}"
            doc_ref = self._db.collection(_IP_USAGE_COLLECTION).document(doc_id)
            doc_ref.set(
                {
                    "client_ip": client_ip,
                    "date": date_key,
                    "count": firestore.Increment(1),
                    "updated_at": self.now(),
                },
                merge=True,
            )
        except GoogleCloudError as exc:
            logger.error("firestore increment_daily_usage failed: %s", type(exc).__name__)
            raise FirestoreError() from exc

    def get_random_existing_urls(self, count: int) -> List[str]:
        """生成済み(status=completed)の画像URLプールから、
        ランダムに count 件のURLを返す。

        プール件数が count 未満の場合は重複を許容して count 件になるまで補う
        (常にちょうど count 件を返す仕様のため)。プールが空の場合は
        空リストを返す。
        """
        self._ensure_initialized()
        try:
            query = self._db.collection(_COLLECTION).where(
                filter=FieldFilter("status", "==", "completed")
            )
            pool: List[str] = []
            for doc in query.stream():
                data = doc.to_dict()
                pool.extend(data.get("image_urls") or [])

            if not pool:
                return []
            if len(pool) >= count:
                return random.sample(pool, count)
            # プール不足時は重複ありで補う
            return random.choices(pool, k=count)
        except GoogleCloudError as exc:
            logger.error("firestore get_random_existing_urls failed: %s", type(exc).__name__)
            raise FirestoreError() from exc

    @staticmethod
    def now() -> datetime:
        return datetime.now(timezone.utc)
