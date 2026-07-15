"""
Retry utilities with exponential backoff, optional jitter, retry predicates,
and circuit breaker protection for the NOESIS agent.
"""

from __future__ import annotations

import asyncio
import inspect
import logging
import random
import time
from dataclasses import dataclass, field
from functools import wraps
from typing import Any, Callable, ParamSpec, TypeVar


P = ParamSpec("P")
T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class RetryConfig:
    """
    Configuration for retry behavior.
    """
    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 30.0
    exponential_base: float = 2.0
    jitter: bool = True
    jitter_min: float = 0.5
    jitter_max: float = 1.5
    retry_on: tuple[type[BaseException], ...] = (Exception,)
    reraise: bool = True

    def __post_init__(self) -> None:
        if self.max_retries < 0:
            raise ValueError("max_retries must be 0 or greater")
        if self.base_delay < 0:
            raise ValueError("base_delay must be 0 or greater")
        if self.max_delay <= 0:
            raise ValueError("max_delay must be greater than 0")
        if self.exponential_base < 1.0:
            raise ValueError("exponential_base must be at least 1.0")
        if self.jitter_min <= 0 or self.jitter_max <= 0:
            raise ValueError("jitter bounds must be greater than 0")
        if self.jitter_min > self.jitter_max:
            raise ValueError("jitter_min cannot be greater than jitter_max")
        if not self.retry_on:
            raise ValueError("retry_on must contain at least one exception type")


def calculate_backoff_delay(config: RetryConfig, attempt_index: int) -> float:
    """
    Calculate the delay for a retry attempt.

    attempt_index is zero-based for the first retry wait.
    """
    delay = min(
        config.base_delay * (config.exponential_base ** attempt_index),
        config.max_delay,
    )
    if config.jitter:
        delay *= random.uniform(config.jitter_min, config.jitter_max)
        delay = min(delay, config.max_delay)
    return max(0.0, delay)


def _should_retry(
    exc: BaseException,
    retry_if: Callable[[BaseException], bool] | None,
) -> bool:
    if retry_if is None:
        return True
    try:
        return bool(retry_if(exc))
    except Exception:
        return False


def with_retry(
    config: RetryConfig | None = None,
    *,
    logger_name: str | None = None,
    retry_if: Callable[[BaseException], bool] | None = None,
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """
    Decorator for retrying sync or async callables with exponential backoff.
    """
    retry_config = config or RetryConfig()

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        logger = logging.getLogger(logger_name or func.__module__)
        function_name = func.__qualname__

        if inspect.iscoroutinefunction(func):
            @wraps(func)
            async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> Any:
                last_exception: BaseException | None = None

                for attempt in range(retry_config.max_retries + 1):
                    try:
                        return await func(*args, **kwargs)
                    except retry_config.retry_on as exc:
                        if not _should_retry(exc, retry_if):
                            raise

                        last_exception = exc
                        is_final_attempt = attempt >= retry_config.max_retries

                        if is_final_attempt:
                            logger.error(
                                "Retry exhausted for %s",
                                function_name,
                                exc_info=True,
                                extra={
                                    "function": function_name,
                                    "attempt": attempt + 1,
                                    "max_retries": retry_config.max_retries,
                                    "error_type": type(exc).__name__,
                                    "error": str(exc)[:500],
                                },
                            )
                            if retry_config.reraise:
                                raise
                            return None

                        delay = calculate_backoff_delay(retry_config, attempt)
                        logger.warning(
                            "Retrying %s after failure",
                            function_name,
                            extra={
                                "function": function_name,
                                "attempt": attempt + 1,
                                "next_delay_seconds": round(delay, 3),
                                "max_retries": retry_config.max_retries,
                                "error_type": type(exc).__name__,
                                "error": str(exc)[:500],
                            },
                        )
                        await asyncio.sleep(delay)

                if last_exception is not None:
                    raise last_exception
                raise RuntimeError(f"Retry loop terminated unexpectedly for {function_name}")

            return async_wrapper

        @wraps(func)
        def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> Any:
            last_exception: BaseException | None = None

            for attempt in range(retry_config.max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except retry_config.retry_on as exc:
                    if not _should_retry(exc, retry_if):
                        raise

                    last_exception = exc
                    is_final_attempt = attempt >= retry_config.max_retries

                    if is_final_attempt:
                        logger.error(
                            "Retry exhausted for %s",
                            function_name,
                            exc_info=True,
                            extra={
                                "function": function_name,
                                "attempt": attempt + 1,
                                "max_retries": retry_config.max_retries,
                                "error_type": type(exc).__name__,
                                "error": str(exc)[:500],
                            },
                        )
                        if retry_config.reraise:
                            raise
                        return None

                    delay = calculate_backoff_delay(retry_config, attempt)
                    logger.warning(
                        "Retrying %s after failure",
                        function_name,
                        extra={
                            "function": function_name,
                            "attempt": attempt + 1,
                            "next_delay_seconds": round(delay, 3),
                            "max_retries": retry_config.max_retries,
                            "error_type": type(exc).__name__,
                            "error": str(exc)[:500],
                        },
                    )
                    time.sleep(delay)

            if last_exception is not None:
                raise last_exception
            raise RuntimeError(f"Retry loop terminated unexpectedly for {function_name}")

        return sync_wrapper

    return decorator


class CircuitBreakerOpenError(RuntimeError):
    """
    Raised when the circuit breaker is open and the call is blocked.
    """


class CircuitBreakerHalfOpenCapacityError(RuntimeError):
    """
    Raised when the half-open state has reached its trial call capacity.
    """


@dataclass(slots=True)
class CircuitBreaker:
    """
    Circuit breaker implementation for async and sync call protection.
    """
    failure_threshold: int = 5
    recovery_timeout: float = 60.0
    half_open_max_calls: int = 3
    expected_exceptions: tuple[type[BaseException], ...] = field(default_factory=lambda: (Exception,))

    STATE_CLOSED = "closed"
    STATE_OPEN = "open"
    STATE_HALF_OPEN = "half_open"

    def __post_init__(self) -> None:
        if self.failure_threshold <= 0:
            raise ValueError("failure_threshold must be greater than 0")
        if self.recovery_timeout <= 0:
            raise ValueError("recovery_timeout must be greater than 0")
        if self.half_open_max_calls <= 0:
            raise ValueError("half_open_max_calls must be greater than 0")
        if not self.expected_exceptions:
            raise ValueError("expected_exceptions must contain at least one exception type")

        self.state: str = self.STATE_CLOSED
        self.failure_count: int = 0
        self.last_failure_time: float | None = None
        self.half_open_calls: int = 0
        self._async_lock = asyncio.Lock()

    def _now(self) -> float:
        return time.monotonic()

    def _transition_to_open(self) -> None:
        self.state = self.STATE_OPEN
        self.last_failure_time = self._now()

    def _transition_to_half_open(self) -> None:
        self.state = self.STATE_HALF_OPEN
        self.half_open_calls = 0

    def _transition_to_closed(self) -> None:
        self.state = self.STATE_CLOSED
        self.failure_count = 0
        self.last_failure_time = None
        self.half_open_calls = 0

    def _check_state_before_call(self) -> None:
        if self.state == self.STATE_OPEN:
            if self.last_failure_time is None:
                self.last_failure_time = self._now()
            elapsed = self._now() - self.last_failure_time
            if elapsed >= self.recovery_timeout:
                self._transition_to_half_open()
            else:
                raise CircuitBreakerOpenError("Circuit breaker is open")

        if self.state == self.STATE_HALF_OPEN:
            if self.half_open_calls >= self.half_open_max_calls:
                raise CircuitBreakerHalfOpenCapacityError(
                    "Circuit breaker half-open trial capacity reached"
                )
            self.half_open_calls += 1

    def _handle_success(self) -> None:
        if self.state in {self.STATE_HALF_OPEN, self.STATE_OPEN}:
            self._transition_to_closed()
        else:
            self.failure_count = 0

    def _handle_failure(self) -> None:
        self.failure_count += 1
        self.last_failure_time = self._now()

        if self.state == self.STATE_HALF_OPEN or self.failure_count >= self.failure_threshold:
            self._transition_to_open()

    async def call(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        async with self._async_lock:
            self._check_state_before_call()

        try:
            if inspect.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
        except self.expected_exceptions:
            async with self._async_lock:
                self._handle_failure()
            raise
        else:
            async with self._async_lock:
                self._handle_success()
            return result

    def decorate(self, func: Callable[P, T]) -> Callable[P, T]:
        if inspect.iscoroutinefunction(func):
            @wraps(func)
            async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> Any:
                return await self.call(func, *args, **kwargs)

            return async_wrapper

        @wraps(func)
        def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> Any:
            raise TypeError(
                "CircuitBreaker.decorate does not support sync wrappers directly. "
                "Use await breaker.call(sync_func, ...) from an async context."
            )

        return sync_wrapper
