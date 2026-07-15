from __future__ import annotations

import json
from datetime import datetime, date
from pathlib import Path
from typing import Any
from uuid import UUID


class NoesisSerializer:
    @staticmethod
    def _default(obj: Any) -> Any:
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        if isinstance(obj, (Path, UUID)):
            return str(obj)
        if hasattr(obj, "model_dump"):
            return obj.model_dump()
        return repr(obj)

    @classmethod
    def to_json(cls, obj: Any, indent: int | None = None) -> str:
        return json.dumps(
            obj,
            ensure_ascii=False,
            default=cls._default,
            indent=indent,
            sort_keys=True,
        )
