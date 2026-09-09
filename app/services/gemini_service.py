"""
GeminiService

設計書 8章「Google AI Studio / Gemini API」/ 51章「サービス責務」に基づく。

責務:
- Gemini API接続
- プロンプト送信
- 画像データ取得
- APIエラー処理

モデルIDは環境変数 GEMINI_IMAGE_MODEL から取得する。
具体的なモデルIDは実装/運用時点でGoogle公式ドキュメントを確認し、
画像生成に対応したモデルを指定すること(このLite版ではデフォルト値を
仮設定しているのみで、正式なモデルIDは公式仕様の確認が必須)。

タイムアウトは google-genai SDK の HttpOptions.timeout(ミリ秒指定)を
使用してSDK/HTTPレイヤーで制御する。この機能は google-genai>=1.0.0 で
利用可能(0.3.0系には存在しないため要注意)。

複数枚生成について:
gemini-2.5-flash-image は GenerateContentConfig の candidateCount /
number_of_images による1リクエストでの複数枚同時生成をサポートしておらず、
指定すると INVALID_ARGUMENT エラーになることを確認済み。
そのため generate_images() は Gemini API を指定枚数分ループ呼び出しする
実装としている(1枚あたり課金が発生する点に注意)。
"""

from __future__ import annotations

import logging
from typing import List

from google import genai
from google.genai import types
from google.genai.errors import APIError

from app.core.exceptions import ImageGenerationAPIError, ImageGenerationTimeoutError

logger = logging.getLogger(__name__)


class GeminiService:
    def __init__(self, api_key: str, model: str, timeout_seconds: int = 300):
        if not api_key:
            logger.warning("GOOGLE_API_KEY is not set. Gemini API calls will fail.")
        self._client = genai.Client(api_key=api_key)
        self._model = model
        # HttpOptions.timeout はミリ秒指定 (google-genai>=1.0.0)
        self._timeout_ms = timeout_seconds * 1000

    def generate_image(self, prompt: str) -> bytes:
        """プロンプトを送信し、生成された画像のバイナリデータを返す。

        通信エラー・生成失敗時は ImageGenerationAPIError /
        ImageGenerationTimeoutError を送出する。二重課金を避けるため、
        本メソッド内では自動リトライは行わない(設計書36章参照)。
        """
        logger.info("gemini image generation started model=%s", self._model)

        try:
            response = self._call_gemini(prompt)
        except TimeoutError as exc:
            # SDK/httpxが接続・読み取りタイムアウト時に送出する例外
            logger.error("gemini image generation timeout")
            raise ImageGenerationTimeoutError() from exc
        except APIError as exc:
            logger.error("gemini api error: %s", getattr(exc, "code", "unknown"))
            raise ImageGenerationAPIError() from exc
        except Exception as exc:  # noqa: BLE001 - 想定外エラーも一律APIエラー扱い
            logger.error("gemini unexpected error: %s", type(exc).__name__)
            raise ImageGenerationAPIError() from exc

        image_bytes = self._extract_image_bytes(response)
        if image_bytes is None:
            logger.error("gemini response contained no image data")
            raise ImageGenerationAPIError("No image data returned from Gemini API.")

        logger.info("gemini image generation completed")
        return image_bytes

    def generate_images(self, prompt: str, count: int) -> List[bytes]:
        """同一プロンプトで指定枚数分の画像を生成する。

        gemini-2.5-flash-image は1リクエストでの複数枚同時生成
        (candidateCount / number_of_images)をサポートしていないため、
        generate_image() を count 回ループ呼び出しする。
        途中で1枚でも失敗した場合は、それまでに生成した分は破棄せず
        例外をそのまま呼び出し元に伝播する(呼び出し元でロールバック等の
        後処理を行う想定)。
        """
        logger.info("gemini batch image generation started count=%d", count)
        images: List[bytes] = []
        for i in range(count):
            logger.info("gemini batch image generation progress %d/%d", i + 1, count)
            images.append(self.generate_image(prompt))
        logger.info("gemini batch image generation completed count=%d", len(images))
        return images

    def _call_gemini(self, prompt: str):
        return self._client.models.generate_content(
            model=self._model,
            contents=prompt,
            config=types.GenerateContentConfig(
                responseModalities=["IMAGE"],
                http_options=types.HttpOptions(timeout=self._timeout_ms),
            ),
        )

    @staticmethod
    def _extract_image_bytes(response) -> bytes | None:
        candidates = getattr(response, "candidates", None) or []
        for candidate in candidates:
            content = getattr(candidate, "content", None)
            if content is None:
                continue
            for part in getattr(content, "parts", None) or []:
                inline_data = getattr(part, "inline_data", None)
                if inline_data is not None and inline_data.data:
                    return inline_data.data
        return None
