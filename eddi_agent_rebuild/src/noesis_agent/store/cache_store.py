from __future__ import annotations

import time
from collections import OrderedDict


class CacheStore:
    """In-memory TTL cache for fast lookups."""

    def __init__(self, max_size: int = 512) -> None:
        self.data: OrderedDict[str, tuple[float, object]] = OrderedDict()
        self.max_size = max_size

    def set(self, key: str, value: object, ttl_seconds: int = 300) -> None:
        expires_at = time.time() + ttl_seconds
        self.data[key] = (expires_at, value)
        self.data.move_to_end(key)
        if len(self.data) > self.max_size:
            self.data.popitem(last=False)

    def get(self, key: str) -> object | None:
        if key not in self.data:
            return None
        expires_at, value = self.data[key]
        if expires_at < time.time():
            del self.data[key]
            return None
        self.data.move_to_end(key)
        return value

    def clear(self) -> None:
        self.data.clear()
