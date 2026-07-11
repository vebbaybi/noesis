from __future__ import annotations

import hashlib
import secrets
import uuid
from typing import Optional


class NoesisID:
    @staticmethod
    def short(prefix: Optional[str] = None) -> str:
        uid = secrets.token_hex(4)
        return f"{prefix}_{uid}" if prefix else uid

    @staticmethod
    def deterministic(value: str, length: int = 12) -> str:
        if not value:
            raise ValueError("Value cannot be empty for deterministic ID")
        return hashlib.sha256(value.encode("utf-8")).hexdigest()[:length]

    @staticmethod
    def session() -> str:
        return uuid.uuid4().hex

    @staticmethod
    def uuid4() -> str:
        return str(uuid.uuid4())