from __future__ import annotations

import re
from typing import Any, List, Optional, Tuple, Union
from urllib.parse import urlparse


class Validator:
    _SESSION_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_]{5,50}$")
    _X_HANDLE_PATTERN = re.compile(r"^[a-zA-Z0-9_]{1,15}$")
    _EMAIL_PATTERN = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")
    _CONTROL_CHARS_PATTERN = re.compile(r"[\x00-\x1f\x7f-\x9f]")
    _WHITESPACE_PATTERN = re.compile(r"\s+")

    @staticmethod
    def session_id(value: str) -> bool:
        if not isinstance(value, str):
            return False
        cleaned = value.strip()
        return bool(cleaned) and Validator._SESSION_ID_PATTERN.fullmatch(cleaned) is not None

    @staticmethod
    def x_handle(handle: str) -> bool:
        if not isinstance(handle, str):
            return False
        cleaned = handle.strip().lstrip("@")
        return bool(cleaned) and Validator._X_HANDLE_PATTERN.fullmatch(cleaned) is not None

    @staticmethod
    def twitter_handle(handle: str) -> bool:
        return Validator.x_handle(handle)

    @staticmethod
    def url(
        url: str, schemes: Optional[Union[List[str], Tuple[str, ...]]] = None
    ) -> bool:
        if not isinstance(url, str):
            return False
        cleaned = url.strip()
        if not cleaned:
            return False
        allowed_schemes = {s.lower() for s in (schemes or ("http", "https"))}
        try:
            parsed = urlparse(cleaned)
        except Exception:
            return False
        if parsed.scheme.lower() not in allowed_schemes:
            return False
        if not parsed.netloc:
            return False
        if any(char.isspace() for char in cleaned):
            return False
        return True

    @staticmethod
    def email(email: str) -> bool:
        if not isinstance(email, str):
            return False
        cleaned = email.strip()
        return bool(cleaned) and Validator._EMAIL_PATTERN.fullmatch(cleaned) is not None

    @staticmethod
    def sanitize(
        text: Any,
        max_length: int = 1000,
        *,
        normalize_whitespace: bool = True,
        strip_control_chars: bool = True,
        ellipsis: str = "...",
    ) -> str:
        if text is None:
            return ""
        if not isinstance(text, str):
            text = str(text)

        cleaned = text
        if strip_control_chars:
            cleaned = Validator._CONTROL_CHARS_PATTERN.sub("", cleaned)
        if normalize_whitespace:
            cleaned = Validator._WHITESPACE_PATTERN.sub(" ", cleaned).strip()

        if max_length < 0:
            raise ValueError("max_length must be >= 0")

        if len(cleaned) > max_length:
            if max_length == 0:
                return ""
            if len(ellipsis) >= max_length:
                return cleaned[:max_length]
            cleaned = cleaned[: max_length - len(ellipsis)].rstrip() + ellipsis

        return cleaned

    @staticmethod
    def required_fields(
        data: dict[str, Any], required: Union[List[str], Tuple[str, ...]]
    ) -> List[str]:
        if not isinstance(data, dict):
            raise TypeError("data must be a dictionary")
        missing: List[str] = []
        for field in required:
            if field not in data:
                missing.append(field)
                continue
            value = data[field]
            if value is None:
                missing.append(field)
            elif isinstance(value, str) and value.strip() == "":
                missing.append(field)
        return missing

    @staticmethod
    def ensure_required_fields(
        data: dict[str, Any], required: Union[List[str], Tuple[str, ...]]
    ) -> None:
        missing = Validator.required_fields(data, required)
        if missing:
            raise ValueError(f"Missing required fields: {', '.join(missing)}")

    @staticmethod
    def non_empty_string(
        value: Any, *, min_length: int = 1, max_length: Optional[int] = None
    ) -> bool:
        if not isinstance(value, str):
            return False
        cleaned = value.strip()
        if len(cleaned) < min_length:
            return False
        if max_length is not None and len(cleaned) > max_length:
            return False
        return True

    @staticmethod
    def positive_int(value: Any, *, allow_zero: bool = False) -> bool:
        if isinstance(value, bool):
            return False
        if not isinstance(value, int):
            return False
        return value >= 0 if allow_zero else value > 0

    @staticmethod
    def positive_float(value: Any, *, allow_zero: bool = False) -> bool:
        if isinstance(value, bool):
            return False
        if not isinstance(value, (int, float)):
            return False
        numeric = float(value)
        return numeric >= 0.0 if allow_zero else numeric > 0.0