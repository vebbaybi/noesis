"""
Unified logging and utility facade for the NOESIS agent.
Provides structured logging, context propagation, async logging, transcript/LLM event logging,
retry execution, timing helpers, validation, error normalization, and Web3/social media awareness.
"""

from __future__ import annotations

import asyncio
import contextvars
import json
import logging
import time
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Optional, ParamSpec, TypeVar, Union

from .constants import (
    ContentLimits,
    DEFAULT_RETRY_POLICY,
    NOESIS_PERSONA,
    LoggingDefaults,
    PLATFORM_CAPABILITIES,
    Platform,
    SessionLimits,
    Timeouts,
)
from .decorators import async_cache, deprecated, singleton
from .errors import (
    APIClientError,
    ConfigurationError,
    DiscordAPIError,
    NoesisError,
    OpenAIAPIError,
    RetryExhaustedError,
    SessionError,
    TimeoutExceededError,
    ValidationError,
    XAPIError,
    handle_noesis_error,
    normalize_exception,
)
from .ids import NoesisID
from .logging import (
    AUDIT_LEVEL,
    METRICS_LEVEL,
    AsyncLogger,
    ContextAdapter,
    CustomLogger,
    SessionLogger,
    configure_logging,
    get_async_logger,
    get_context_logger,
    get_logger,
    get_session_logger,
    log_performance,
    redact_sensitive_data,
    reset_session_context,
    reset_trace_id,
    set_session_context,
    set_trace_id,
)
from .retry import (
    CircuitBreaker,
    CircuitBreakerHalfOpenCapacityError,
    CircuitBreakerOpenError,
    RetryConfig,
    calculate_backoff_delay,
    with_retry,
)
from .timing import (
    PerformanceTracker,
    Timer,
    ameasure_time,
    measure_time,
    timed,
)
from .validators import (
    Validator,
)

P = ParamSpec("P")
T = TypeVar("T")


@dataclass
class Web3LogContext:
    wallet_address: Optional[str] = None
    transaction_hash: Optional[str] = None
    chain_id: Optional[int] = None
    contract_address: Optional[str] = None
    token_symbol: Optional[str] = None
    amount: Optional[str] = None
    network_name: Optional[str] = None


class NoesisLogger:
    """
    Unified facade for all NOESIS utility operations.

    This class provides a single entry point for logging, retry, timing, validation,
    error handling, and Web3/social media context management. It automatically
    propagates trace IDs, session IDs, and optional Web3 context across async tasks.
    """

    _instance: Optional[NoesisLogger] = None
    _lock = asyncio.Lock()

    def __init__(
        self,
        logger_name: str = "noesis_agent",
        *,
        configure_on_init: bool = False,
        level: Optional[str] = None,
        env: str = "development",
        service_name: Optional[str] = None,
        log_dir: Union[str, Path] = "logs",
        enable_json: bool = False,
        enable_alerts: bool = False,
        alert_webhook: Optional[str] = None,
        discord_webhook: Optional[str] = None,
        rate_limit: Optional[tuple[int, int]] = None,
        sentry_dsn: Optional[str] = None,
    ) -> None:
        self.logger_name = logger_name
        self.service_name = service_name or logger_name
        self.env = env
        self._web3_context: contextvars.ContextVar[Optional[Web3LogContext]] = contextvars.ContextVar(
            "noesis_web3_context", default=None
        )
        self._sentry_initialized = False

        if configure_on_init:
            resolved_level = level or LoggingDefaults.ENVIRONMENT_LOG_LEVELS.get(env, "INFO")
            self._logger = configure_logging(
                level=resolved_level,
                env=env,
                service_name=self.service_name,
                log_dir=str(log_dir),
                enable_json=enable_json,
                enable_alerts=enable_alerts,
                alert_webhook=alert_webhook or discord_webhook,
                rate_limit=rate_limit,
            )
        else:
            self._logger = get_logger(logger_name)

        if sentry_dsn:
            self._init_sentry(sentry_dsn)

    @classmethod
    async def get_instance(cls, **kwargs) -> NoesisLogger:
        async with cls._lock:
            if cls._instance is None:
                cls._instance = cls(**kwargs)
            return cls._instance

    @property
    def logger(self) -> logging.Logger:
        return self._logger

    def _init_sentry(self, dsn: str) -> None:
        try:
            import sentry_sdk
            from sentry_sdk.integrations.logging import LoggingIntegration
            sentry_logging = LoggingIntegration(
                level=logging.INFO,
                event_level=logging.ERROR,
            )
            sentry_sdk.init(
                dsn=dsn,
                environment=self.env,
                integrations=[sentry_logging],
                traces_sample_rate=1.0 if self.env == "production" else 0.1,
            )
            self._sentry_initialized = True
        except ImportError:
            self._logger.debug("sentry_sdk is not installed; Sentry logging disabled")

    def configure(
        self,
        *,
        level: str = "INFO",
        env: Optional[str] = None,
        service_name: Optional[str] = None,
        log_dir: Union[str, Path] = "logs",
        enable_json: bool = False,
        enable_alerts: bool = False,
        alert_webhook: Optional[str] = None,
        rate_limit: Optional[tuple[int, int]] = None,
    ) -> logging.Logger:
        self.env = env or self.env
        self._logger = configure_logging(
            level=level,
            env=self.env,
            service_name=service_name or self.service_name,
            log_dir=str(log_dir),
            enable_json=enable_json,
            enable_alerts=enable_alerts,
            alert_webhook=alert_webhook,
            rate_limit=rate_limit,
        )
        return self._logger

    def child(self, name: str) -> logging.Logger:
        return get_logger(name)

    def context(self, **context: Any) -> ContextAdapter:
        return get_context_logger(self.logger.name, **context)

    def session_logger(self) -> SessionLogger:
        return get_session_logger(self.logger.name)

    def async_logger(self, max_queue_size: int = 10000) -> AsyncLogger:
        return AsyncLogger(self.logger.name, max_queue_size=max_queue_size)

    def set_web3_context(self, **kwargs: Any) -> contextvars.Token[Optional[Web3LogContext]]:
        ctx = Web3LogContext(**{k: v for k, v in kwargs.items() if hasattr(Web3LogContext, k)})
        return self._web3_context.set(ctx)

    def reset_web3_context(self, token: contextvars.Token[Optional[Web3LogContext]]) -> None:
        self._web3_context.reset(token)

    def _inject_web3_context(self, extra: dict[str, Any]) -> dict[str, Any]:
        ctx = self._web3_context.get()
        if ctx:
            for field, value in ctx.__dict__.items():
                if value is not None:
                    extra[f"web3_{field}"] = value
        return extra

    def _build_extra(self, **kwargs: Any) -> Optional[dict[str, Any]]:
        if not kwargs:
            return None
        extra = redact_sensitive_data(dict(kwargs))
        extra = self._inject_web3_context(extra)
        return extra

    def debug(self, message: str, **extra: Any) -> None:
        self.logger.debug(message, extra=self._build_extra(**extra))

    def info(self, message: str, **extra: Any) -> None:
        self.logger.info(message, extra=self._build_extra(**extra))

    def audit(self, message: str, **extra: Any) -> None:
        self.logger.log(AUDIT_LEVEL, message, extra=self._build_extra(**extra))

    def warning(self, message: str, **extra: Any) -> None:
        self.logger.warning(message, extra=self._build_extra(**extra))

    def metrics(self, message: str, **extra: Any) -> None:
        self.logger.log(METRICS_LEVEL, message, extra=self._build_extra(**extra))

    def error(
        self,
        message: str,
        *,
        exc_info: Union[bool, BaseException] = False,
        **extra: Any,
    ) -> None:
        if isinstance(exc_info, BaseException):
            self.logger.error(message, exc_info=(type(exc_info), exc_info, exc_info.__traceback__), extra=self._build_extra(**extra))
            return
        self.logger.error(message, exc_info=exc_info, extra=self._build_extra(**extra))

    def critical(
        self,
        message: str,
        *,
        exc_info: Union[bool, BaseException] = False,
        **extra: Any,
    ) -> None:
        if isinstance(exc_info, BaseException):
            self.logger.critical(message, exc_info=(type(exc_info), exc_info, exc_info.__traceback__), extra=self._build_extra(**extra))
            return
        self.logger.critical(message, exc_info=exc_info, extra=self._build_extra(**extra))

    def exception(self, message: str, **extra: Any) -> None:
        self.logger.exception(message, extra=self._build_extra(**extra))

    @contextmanager
    def trace_span(self, name: str, **attributes: Any):
        trace_id = NoesisID.short()
        token = set_trace_id(trace_id)
        start = time.perf_counter()
        self.debug(f"Span start: {name}", trace_id=trace_id, **attributes)
        try:
            yield trace_id
        except Exception as e:
            self.error(f"Span failed: {name}", exc_info=e, trace_id=trace_id, duration_ms=(time.perf_counter() - start) * 1000)
            raise
        finally:
            reset_trace_id(token)
            self.debug(f"Span end: {name}", trace_id=trace_id, duration_ms=(time.perf_counter() - start) * 1000)

    @asynccontextmanager
    async def atrace_span(self, name: str, **attributes: Any):
        trace_id = NoesisID.short()
        token = set_trace_id(trace_id)
        start = time.perf_counter()
        self.debug(f"Async span start: {name}", trace_id=trace_id, **attributes)
        try:
            yield trace_id
        except Exception as e:
            self.error(f"Async span failed: {name}", exc_info=e, trace_id=trace_id, duration_ms=(time.perf_counter() - start) * 1000)
            raise
        finally:
            reset_trace_id(token)
            self.debug(f"Async span end: {name}", trace_id=trace_id, duration_ms=(time.perf_counter() - start) * 1000)

    def bind_trace_id(self, trace_id: Optional[str] = None):
        trace_id = trace_id or NoesisID.short()
        return set_trace_id(trace_id)

    def unbind_trace_id(self, token: Any) -> None:
        reset_trace_id(token)

    def bind_session(
        self,
        *,
        session_id: Optional[str] = None,
        room_id: Optional[str] = None,
        speaker: Optional[str] = None,
    ) -> dict[str, Any]:
        session_id = session_id or NoesisID.session()
        return set_session_context(session_id=session_id, room_id=room_id, speaker=speaker)

    def unbind_session(self, tokens: Mapping[str, Any]) -> None:
        reset_session_context(tokens)

    def log_transcript(
        self,
        *,
        session_id: str,
        speaker: str,
        text: str,
        room_id: Optional[str] = None,
        trace_id: Optional[str] = None,
        **extra: Any,
    ) -> None:
        self.session_logger().log_transcript(
            session_id=session_id,
            speaker=speaker,
            text=text,
            room_id=room_id,
            trace_id=trace_id,
            **extra,
        )

    def log_llm_call(
        self,
        *,
        session_id: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        latency_ms: float,
        room_id: Optional[str] = None,
        trace_id: Optional[str] = None,
        **extra: Any,
    ) -> None:
        self.session_logger().log_llm_call(
            session_id=session_id,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            latency_ms=latency_ms,
            room_id=room_id,
            trace_id=trace_id,
            **extra,
        )

    def log_web3_transaction(
        self,
        *,
        session_id: str,
        wallet: str,
        tx_hash: str,
        chain_id: int,
        status: str,
        gas_used: Optional[int] = None,
        block_number: Optional[int] = None,
        **extra: Any,
    ) -> None:
        payload = {
            "session_id": session_id,
            "wallet_address": wallet,
            "transaction_hash": tx_hash,
            "chain_id": chain_id,
            "status": status,
            "gas_used": gas_used,
            "block_number": block_number,
            "type": "web3_transaction",
            **extra,
        }
        self.metrics("Web3 transaction", **payload)

    def log_social_event(
        self,
        *,
        platform: str,
        event_type: str,
        user_id: str,
        content_preview: str,
        room_id: Optional[str] = None,
        **extra: Any,
    ) -> None:
        payload = {
            "platform": platform,
            "event_type": event_type,
            "user_id": user_id,
            "content_preview": content_preview[:200],
            "room_id": room_id,
            "type": "social_event",
            **extra,
        }
        self.info("Social platform event", **payload)

    def timer(self) -> Timer:
        return Timer()

    @contextmanager
    def measure(
        self,
        name: str,
        *,
        level: int = logging.DEBUG,
        extra: Optional[dict[str, Any]] = None,
    ):
        with measure_time(name, self.logger, level=level, extra=extra) as t:
            yield t

    @asynccontextmanager
    async def ameasure(
        self,
        name: str,
        *,
        level: int = logging.DEBUG,
        extra: Optional[dict[str, Any]] = None,
    ):
        async with ameasure_time(name, self.logger, level=level, extra=extra) as t:
            yield t

    def tracker(self, name: str, **metadata: Any) -> PerformanceTracker:
        tracker = PerformanceTracker(name=name)
        tracker.metadata.update(metadata)
        return tracker

    def retry_config(
        self,
        *,
        max_retries: int = DEFAULT_RETRY_POLICY.max_retries,
        base_delay: float = DEFAULT_RETRY_POLICY.base_delay_seconds,
        max_delay: float = DEFAULT_RETRY_POLICY.max_delay_seconds,
        exponential_base: float = DEFAULT_RETRY_POLICY.backoff_multiplier,
        jitter: bool = DEFAULT_RETRY_POLICY.jitter_enabled,
        jitter_min: float = 0.5,
        jitter_max: float = 1.5,
        retry_on: tuple[type[BaseException], ...] = (Exception,),
        reraise: bool = True,
    ) -> RetryConfig:
        return RetryConfig(
            max_retries=max_retries,
            base_delay=base_delay,
            max_delay=max_delay,
            exponential_base=exponential_base,
            jitter=jitter,
            jitter_min=jitter_min,
            jitter_max=jitter_max,
            retry_on=retry_on,
            reraise=reraise,
        )

    def retry(
        self,
        func=None,
        *,
        config: Optional[RetryConfig] = None,
        retry_if=None,
    ):
        decorator = with_retry(
            config=config or self.retry_config(),
            logger_name=self.logger.name,
            retry_if=retry_if,
        )
        if func is None:
            return decorator
        return decorator(func)

    async def run_with_retry(
        self,
        func,
        *args: Any,
        config: Optional[RetryConfig] = None,
        retry_if=None,
        **kwargs: Any,
    ) -> Any:
        wrapped = self.retry(config=config, retry_if=retry_if)(func)
        return await wrapped(*args, **kwargs)

    def breaker(
        self,
        *,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        half_open_max_calls: int = 3,
        expected_exceptions: tuple[type[BaseException], ...] = (Exception,),
    ) -> CircuitBreaker:
        return CircuitBreaker(
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
            half_open_max_calls=half_open_max_calls,
            expected_exceptions=expected_exceptions,
        )

    def validate_session_id(self, session_id: str) -> bool:
        return Validator.session_id(session_id)

    def validate_x_handle(self, handle: str) -> bool:
        return Validator.x_handle(handle)

    def validate_twitter_handle(self, handle: str) -> bool:
        return Validator.twitter_handle(handle)

    def validate_url(self, url: str, schemes: Optional[Union[list[str], tuple[str, ...]]] = None) -> bool:
        return Validator.url(url, schemes=schemes)

    def validate_email(self, email: str) -> bool:
        return Validator.email(email)

    def validate_required_fields(
        self,
        data: dict[str, Any],
        required_fields: Union[list[str], tuple[str, ...]],
    ) -> list[str]:
        return Validator.required_fields(data, required_fields)

    def ensure_required_fields(
        self,
        data: dict[str, Any],
        required_fields: Union[list[str], tuple[str, ...]],
    ) -> None:
        Validator.ensure_required_fields(data, required_fields)

    def validate_non_empty_string(
        self,
        value: Any,
        *,
        min_length: int = 1,
        max_length: Optional[int] = None,
    ) -> bool:
        return Validator.non_empty_string(value, min_length=min_length, max_length=max_length)

    def validate_positive_int(self, value: Any, *, allow_zero: bool = False) -> bool:
        return Validator.positive_int(value, allow_zero=allow_zero)

    def validate_positive_float(self, value: Any, *, allow_zero: bool = False) -> bool:
        return Validator.positive_float(value, allow_zero=allow_zero)

    def sanitize(self, text: Any, max_length: int = 1000) -> str:
        return Validator.sanitize(text, max_length=max_length)

    def normalize_error(
        self,
        exc: Exception,
        *,
        function_name: Optional[str] = None,
    ) -> NoesisError:
        return normalize_exception(exc, function_name=function_name)

    def raise_validation_error(
        self,
        message: str,
        *,
        field: Optional[str] = None,
        value: Any = None,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        raise ValidationError(message, field=field, value=value, details=details)

    def raise_session_error(
        self,
        message: str,
        *,
        session_id: Optional[str] = None,
        room_id: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        raise SessionError(message, session_id=session_id, room_id=room_id, details=details)

    def raise_config_error(
        self,
        message: str,
        *,
        missing_key: Optional[str] = None,
        invalid_key: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        raise ConfigurationError(message, missing_key=missing_key, invalid_key=invalid_key, details=details)

    def raise_api_error(
        self,
        message: str,
        *,
        service: str,
        status_code: Optional[int] = None,
        response: Optional[str] = None,
        endpoint: Optional[str] = None,
        retryable: Optional[bool] = None,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        raise APIClientError(
            message,
            service=service,
            status_code=status_code,
            response=response,
            endpoint=endpoint,
            retryable=retryable,
            details=details,
        )

    def generate_id(self, prefix: Optional[str] = None) -> str:
        return NoesisID.short(prefix)

    def generate_session_id(self) -> str:
        return NoesisID.session()

    @property
    def persona(self):
        return NOESIS_PERSONA

    @property
    def platform_capabilities(self):
        return PLATFORM_CAPABILITIES

    @property
    def session_limits(self):
        return SessionLimits

    @property
    def content_limits(self):
        return ContentLimits

    @property
    def timeouts(self):
        return Timeouts

    def platform_max_length(self, platform: Platform) -> int:
        return PLATFORM_CAPABILITIES[platform].max_content_length

    def supported_platforms(self) -> tuple[Platform, ...]:
        return tuple(PLATFORM_CAPABILITIES.keys())


_default_noesis_logger: Optional[NoesisLogger] = None


def get_noesis_logger(name: str = "noesis_agent") -> NoesisLogger:
    global _default_noesis_logger
    if _default_noesis_logger is None or _default_noesis_logger.logger_name != name:
        _default_noesis_logger = NoesisLogger(name)
    return _default_noesis_logger


__all__ = [
    "NoesisLogger",
    "get_noesis_logger",
    "Web3LogContext",
    "async_cache",
    "deprecated",
    "singleton",
    "configure_logging",
    "get_logger",
    "get_context_logger",
    "get_session_logger",
    "get_async_logger",
    "CustomLogger",
    "ContextAdapter",
    "SessionLogger",
    "AsyncLogger",
    "log_performance",
    "AUDIT_LEVEL",
    "METRICS_LEVEL",
    "NoesisError",
    "ConfigurationError",
    "APIClientError",
    "OpenAIAPIError",
    "XAPIError",
    "DiscordAPIError",
    "SessionError",
    "ValidationError",
    "RetryExhaustedError",
    "TimeoutExceededError",
    "handle_noesis_error",
    "normalize_exception",
    "with_retry",
    "RetryConfig",
    "CircuitBreaker",
    "CircuitBreakerOpenError",
    "CircuitBreakerHalfOpenCapacityError",
    "calculate_backoff_delay",
    "Timer",
    "measure_time",
    "ameasure_time",
    "PerformanceTracker",
    "timed",
    "Validator",
    "Platform",
    "PLATFORM_CAPABILITIES",
    "SessionLimits",
    "ContentLimits",
    "Timeouts",
    "DEFAULT_RETRY_POLICY",
    "NOESIS_PERSONA",
]
