from __future__ import annotations

import asyncio
import hashlib
import importlib.util
import time

from noesis_agent.domain.contracts.intelligence import CapabilityHealth, CapabilityState


class LocalIdempotencyStore:
    def __init__(self, *, maximum_keys: int = 10_000) -> None:
        self._keys: dict[str, float] = {}
        self._lock = asyncio.Lock()
        self._maximum_keys = maximum_keys

    async def claim(self, tenant_id: str, event_id: str, *, ttl_seconds: int) -> bool:
        key = hashlib.sha256(f"{tenant_id}\0{event_id}".encode()).hexdigest()
        now = time.monotonic()
        async with self._lock:
            self._keys = {item: expiry for item, expiry in self._keys.items() if expiry > now}
            if key in self._keys:
                return False
            if len(self._keys) >= self._maximum_keys:
                oldest = min(self._keys, key=self._keys.__getitem__)
                del self._keys[oldest]
            self._keys[key] = now + ttl_seconds
            return True

    def health(self) -> CapabilityHealth:
        return CapabilityHealth(name="idempotency", state=CapabilityState.DEGRADED,
                                detail="process-local; duplicates across replicas are not coordinated")


class RedisIdempotencyStore:
    def __init__(self, url: str, *, namespace: str = "noesis", operation_timeout: float = 1.0) -> None:
        self._url = url
        self._namespace = namespace
        self._timeout = operation_timeout
        self._client: object | None = None
        self._fallback = LocalIdempotencyStore()
        self._degraded = False

    async def claim(self, tenant_id: str, event_id: str, *, ttl_seconds: int) -> bool:
        if not self._url or importlib.util.find_spec("redis") is None:
            self._degraded = True
            return await self._fallback.claim(tenant_id, event_id, ttl_seconds=ttl_seconds)
        try:
            if self._client is None:
                import redis.asyncio as redis
                self._client = redis.from_url(self._url, decode_responses=True,
                                              socket_connect_timeout=self._timeout,
                                              socket_timeout=self._timeout)
            tenant = hashlib.sha256(tenant_id.encode()).hexdigest()[:24]
            event = hashlib.sha256(event_id.encode()).hexdigest()
            key = f"{self._namespace}:idempotency:{tenant}:{event}"
            async with asyncio.timeout(self._timeout):
                claimed = await self._client.set(key, "1", ex=ttl_seconds, nx=True)  # type: ignore[attr-defined]
            self._degraded = False
            return bool(claimed)
        except (OSError, asyncio.TimeoutError):
            self._degraded = True
            return await self._fallback.claim(tenant_id, event_id, ttl_seconds=ttl_seconds)

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()  # type: ignore[attr-defined]

    def health(self) -> CapabilityHealth:
        state = CapabilityState.DEGRADED if self._degraded or not self._url else CapabilityState.READY
        return CapabilityHealth(name="redis", state=state,
                                detail="local idempotency fallback active" if state is CapabilityState.DEGRADED else "connected")
