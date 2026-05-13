from __future__ import annotations

import re
import unicodedata


class TextUtil:
    _WHITESPACE_PATTERN = re.compile(r"\s+")
    _SLUG_INVALID_PATTERN = re.compile(r"[^\w\s-]")
    _SLUG_HYPHEN_PATTERN = re.compile(r"[-\s]+")

    @staticmethod
    def normalize_whitespace(text: str) -> str:
        if not text:
            return ""
        return TextUtil._WHITESPACE_PATTERN.sub(" ", text).strip()

    @staticmethod
    def slugify(text: str) -> str:
        normalized = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
        normalized = TextUtil._SLUG_INVALID_PATTERN.sub("", normalized).lower()
        return TextUtil._SLUG_HYPHEN_PATTERN.sub("-", normalized).strip("-")

    @staticmethod
    def truncate(text: str, length: int, suffix: str = "...") -> str:
        if len(text) <= length:
            return text
        if length <= len(suffix):
            return suffix[:length]
        truncated = text[: length - len(suffix)].rsplit(" ", 1)[0]
        return truncated + suffix