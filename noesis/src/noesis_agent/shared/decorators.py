from __future__ import annotations

import asyncio
import hashlib
import inspect
import logging
import pickle
import threading
import time
import warnings
from dataclasses import dataclass
from functools import wraps
from typing import Any, Callable, Coroutine, ParamSpec, TypeVar, cast

P = ParamSpec("P")
T = TypeVar("T")


@dataclass(slots=True)
class _CacheEntry:
    value: Any
    expires_at: float


def _build_cache_key(
    func: Callable[..., Any],
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
) -> str:
    qualified_name = f"{func.__module__}.{func.__qualname__}"
    try:
        payload = pickle.dumps(
            (qualified_name, args, tuple(sorted(kwargs.items()))),
            protocol=pickle.HIGHEST_PROTOCOL,
        )
    except Exception:
        fallback = repr((qualified_name, args, sorted(kwargs.items())))
        payload = fallback.encode("utf-8", errors="replace")
    digest = hashlib.sha256(payload).hexdigest()
    return f"{qualified_name}:{digest}"


def async_cache(
    ttl_seconds: int = 300,
    max_entries: int = 512,
) -> Callable[[Callable[P, Coroutine[Any, Any, T]]], Callable[P, Coroutine[Any, Any, T]]]:
    if ttl_seconds <= 0:
        raise ValueError("ttl_seconds must be greater than 0")
    if max_entries <= 0:
        raise ValueError("max_entries must be greater than 0")

    cache: dict[str, _CacheEntry] = {}
    locks: dict[str, asyncio.Lock] = {}
    state_lock = asyncio.Lock()

    def _prune_expired(now: float) -> None:
        expired_keys = [key for key, entry in cache.items() if entry.expires_at <= now]
        for key in expired_keys:
            cache.pop(key, None)
            locks.pop(key, None)

    def _enforce_size_limit() -> None:
        if len(cache) <= max_entries:
            return
        overflow = len(cache) - max_entries
        keys_to_remove = list(cache.keys())[:overflow]
        for key in keys_to_remove:
            cache.pop(key, None)
            locks.pop(key, None)

    def decorator(func: Callable[P, Coroutine[Any, Any, T]]) -> Callable[P, Coroutine[Any, Any, T]]:
        if not inspect.iscoroutinefunction(func):
            raise TypeError("async_cache can only be applied to async functions")

        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            now = time.monotonic()
            key = _build_cache_key(func, args, dict(kwargs))

            async with state_lock:
                _prune_expired(now)
                entry = cache.get(key)
                if entry is not None and entry.expires_at > now:
                    return cast(T, entry.value)
                lock = locks.get(key)
                if lock is None:
                    lock = asyncio.Lock()
                    locks[key] = lock

            async with lock:
                now = time.monotonic()
                async with state_lock:
                    entry = cache.get(key)
                    if entry is not None and entry.expires_at > now:
                        return cast(T, entry.value)

                result = await func(*args, **kwargs)

                async with state_lock:
                    cache[key] = _CacheEntry(
                        value=result,
                        expires_at=time.monotonic() + ttl_seconds,
                    )
                    _enforce_size_limit()

                return result

        def cache_clear() -> None:
            cache.clear()
            locks.clear()

        def cache_info() -> dict[str, int]:
            now = time.monotonic()
            live_entries = sum(1 for entry in cache.values() if entry.expires_at > now)
            expired_entries = len(cache) - live_entries
            return {
                "entries": len(cache),
                "live_entries": live_entries,
                "expired_entries": expired_entries,
                "max_entries": max_entries,
                "ttl_seconds": ttl_seconds,
            }

        setattr(wrapper, "cache_clear", cache_clear)
        setattr(wrapper, "cache_info", cache_info)
        return wrapper

    return decorator


def singleton(cls: type[T]) -> Callable[..., T]:
    instance: T | None = None
    lock = threading.Lock()

    @wraps(cls)
    def get_instance(*args: Any, **kwargs: Any) -> T:
        nonlocal instance
        if instance is None:
            with lock:
                if instance is None:
                    instance = cls(*args, **kwargs)
        return instance

    return get_instance


def deprecated(
    message: str | None = None,
    *,
    category: type[Warning] = DeprecationWarning,
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        logger = logging.getLogger(func.__module__)
        warning_message = f"{func.__module__}.{func.__qualname__} is deprecated"
        if message:
            warning_message = f"{warning_message}: {message}"

        if inspect.iscoroutinefunction(func):

            @wraps(func)
            async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> Any:
                warnings.warn(warning_message, category=category, stacklevel=2)
                logger.warning(warning_message)
                return await cast(Callable[P, Coroutine[Any, Any, Any]], func)(*args, **kwargs)

            return cast(Callable[P, T], async_wrapper)

        @wraps(func)
        def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> Any:
            warnings.warn(warning_message, category=category, stacklevel=2)
            logger.warning(warning_message)
            return func(*args, **kwargs)

        return cast(Callable[P, T], sync_wrapper)

    return decorator


__all__ = [
    "async_cache",
    "deprecated",
    "singleton",
]
