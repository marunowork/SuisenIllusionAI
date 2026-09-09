"""
PromptService

設計書 9章「プロンプト設計」/ 51章「サービス責務」に基づく。

責務:
- keyword validation
- keyword normalization
- prompt generation

初期版ではLLMによるプロンプト拡張を行わず、
FastAPI内部の固定テンプレートを使用する。
将来的にGeminiによるプロンプト拡張を追加可能な形にしておく。
"""

from __future__ import annotations

import logging
import unicodedata

from app.core.exceptions import InvalidRequestError

logger = logging.getLogger(__name__)

_PROMPT_TEMPLATE = (
    "Create a high-quality photorealistic image of {keyword}.\n"
    "Natural lighting.\n"
    "Detailed and true-to-life textures.\n"
    "Soft background.\n"
    "High resolution.\n"
    "Photorealistic."
)


class PromptService:
    """keywordの検証・正規化・プロンプト生成を担当する。"""

    def validate_keyword(self, keyword: str) -> str:
        if keyword is None:
            raise InvalidRequestError("keyword is required.")

        normalized = self.normalize_keyword(keyword)

        if len(normalized) < 1:
            raise InvalidRequestError("keyword must not be empty.")
        if len(normalized) > 100:
            raise InvalidRequestError("keyword must be 100 characters or fewer.")
        if any(ord(ch) < 0x20 or ord(ch) == 0x7F for ch in normalized):
            raise InvalidRequestError("keyword contains control characters.")

        return normalized

    def normalize_keyword(self, keyword: str) -> str:
        """全角/半角の揺れなどを正規化し、前後の空白を除去する。"""
        normalized = unicodedata.normalize("NFKC", keyword)
        return normalized.strip()

    def build_prompt(self, keyword: str) -> str:
        """テンプレートに基づきプロンプトを生成する。

        将来的にGemini自体でプロンプト拡張を行う場合は、
        ここでGeminiService経由の拡張処理に差し替える。
        """
        validated_keyword = self.validate_keyword(keyword)
        prompt = _PROMPT_TEMPLATE.format(keyword=validated_keyword)
        logger.info("prompt generated keyword=%s", validated_keyword)
        return prompt
