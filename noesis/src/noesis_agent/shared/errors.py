from __future__ import annotations

import asyncio
import inspect
import logging
from functools import wraps
from typing import Any, Callable, Optional, ParamSpec, TypeVar

P = ParamSpec("P")
T = TypeVar("T")


class NoesisError(Exception):
    default_code = "NOESIS_ERROR"

    def __init__(
        self,
        message: str,
        *,
        code: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        self.message = str(message)
        self.code = code or self.default_code
        self.details = dict(details or {})
        super().__init__(self.message)

    def to_dict(self) -> dict[str, Any]:
        return {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "code": self.code,
            "details": self.details,
        }

    def __str__(self) -> str:
        if self.details:
            return f"{self.code}: {self.message} | details={self.details}"
        return f"{self.code}: {self.message}"


class ConfigurationError(NoesisError):
    default_code = "CONFIG_ERROR"

    def __init__(
        self,
        message: str,
        *,
        missing_key: Optional[str] = None,
        invalid_key: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        payload = dict(details or {})
        if missing_key is not None:
            payload["missing_key"] = missing_key
        if invalid_key is not None:
            payload["invalid_key"] = invalid_key
        super().__init__(message, code=self.default_code, details=payload)


class APIClientError(NoesisError):
    default_code = "API_CLIENT_ERROR"

    def __init__(
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
        payload = dict(details or {})
        payload["service"] = service
        if status_code is not None:
            payload["status_code"] = status_code
        if response is not None:
            payload["response"] = str(response)[:500]
        if endpoint is not None:
            payload["endpoint"] = endpoint
        if retryable is not None:
            payload["retryable"] = retryable
        normalized = service.strip().upper().replace(" ", "_")
        code = f"{normalized}_API_ERROR"
        super().__init__(message, code=code, details=payload)


class OpenAIAPIError(APIClientError):
    def __init__(
        self,
        message: str,
        *,
        model: Optional[str] = None,
        status_code: Optional[int] = None,
        response: Optional[str] = None,
        endpoint: Optional[str] = None,
        retryable: Optional[bool] = None,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        payload = dict(details or {})
        if model is not None:
            payload["model"] = model
        super().__init__(
            message,
            service="openai",
            status_code=status_code,
            response=response,
            endpoint=endpoint,
            retryable=retryable,
            details=payload,
        )


class XAPIError(APIClientError):
    def __init__(
        self,
        message: str,
        *,
        endpoint: Optional[str] = None,
        status_code: Optional[int] = None,
        response: Optional[str] = None,
        retryable: Optional[bool] = None,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message,
            service="x",
            status_code=status_code,
            response=response,
            endpoint=endpoint,
            retryable=retryable,
            details=details,
        )


class DiscordAPIError(APIClientError):
    def __init__(
        self,
        message: str,
        *,
        endpoint: Optional[str] = None,
        status_code: Optional[int] = None,
        response: Optional[str] = None,
        retryable: Optional[bool] = None,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message,
            service="discord",
            status_code=status_code,
            response=response,
            endpoint=endpoint,
            retryable=retryable,
            details=details,
        )


class YouTubeAPIError(APIClientError):
    def __init__(
        self,
        message: str,
        *,
        endpoint: Optional[str] = None,
        status_code: Optional[int] = None,
        response: Optional[str] = None,
        retryable: Optional[bool] = None,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message,
            service="youtube",
            status_code=status_code,
            response=response,
            endpoint=endpoint,
            retryable=retryable,
            details=details,
        )


class SpotifyAPIError(APIClientError):
    def __init__(
        self,
        message: str,
        *,
        endpoint: Optional[str] = None,
        status_code: Optional[int] = None,
        response: Optional[str] = None,
        retryable: Optional[bool] = None,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message,
            service="spotify",
            status_code=status_code,
            response=response,
            endpoint=endpoint,
            retryable=retryable,
            details=details,
        )


class Web3Error(NoesisError):
    default_code = "WEB3_ERROR"

    def __init__(
        self,
        message: str,
        *,
        chain_id: Optional[int] = None,
        contract_address: Optional[str] = None,
        transaction_hash: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        payload = dict(details or {})
        if chain_id is not None:
            payload["chain_id"] = chain_id
        if contract_address is not None:
            payload["contract_address"] = contract_address
        if transaction_hash is not None:
            payload["transaction_hash"] = transaction_hash
        super().__init__(message, code=self.default_code, details=payload)


class SessionError(NoesisError):
    default_code = "SESSION_ERROR"

    def __init__(
        self,
        message: str,
        *,
        session_id: Optional[str] = None,
        room_id: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        payload = dict(details or {})
        if session_id is not None:
            payload["session_id"] = session_id
        if room_id is not None:
            payload["room_id"] = room_id
        super().__init__(message, code=self.default_code, details=payload)


class ValidationError(NoesisError):
    default_code = "VALIDATION_ERROR"

    def __init__(
        self,
        message: str,
        *,
        field: Optional[str] = None,
        value: Any = None,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        payload = dict(details or {})
        if field is not None:
            payload["field"] = field
        if value is not None:
            payload["value"] = repr(value)[:250]
        super().__init__(message, code=self.default_code, details=payload)


class RetryExhaustedError(NoesisError):
    default_code = "RETRY_EXHAUSTED"

    def __init__(
        self,
        message: str,
        *,
        attempts: int,
        last_error: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        payload = dict(details or {})
        payload["attempts"] = attempts
        if last_error is not None:
            payload["last_error"] = last_error[:500]
        super().__init__(message, code=self.default_code, details=payload)


class TimeoutExceededError(NoesisError):
    default_code = "TIMEOUT_EXCEEDED"

    def __init__(
        self,
        message: str,
        *,
        timeout_seconds: float,
        operation: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        payload = dict(details or {})
        payload["timeout_seconds"] = timeout_seconds
        if operation is not None:
            payload["operation"] = operation
        super().__init__(message, code=self.default_code, details=payload)


class RateLimitError(NoesisError):
    default_code = "RATE_LIMIT_ERROR"

    def __init__(
        self,
        message: str,
        *,
        retry_after: Optional[float] = None,
        limit: Optional[int] = None,
        remaining: Optional[int] = None,
        reset_at: Optional[float] = None,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        payload = dict(details or {})
        if retry_after is not None:
            payload["retry_after"] = retry_after
        if limit is not None:
            payload["limit"] = limit
        if remaining is not None:
            payload["remaining"] = remaining
        if reset_at is not None:
            payload["reset_at"] = reset_at
        super().__init__(message, code=self.default_code, details=payload)


class ModerationViolationError(NoesisError):
    default_code = "MODERATION_VIOLATION"

    def __init__(
        self,
        message: str,
        *,
        category: Optional[str] = None,
        confidence: Optional[float] = None,
        flagged_content: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        payload = dict(details or {})
        if category is not None:
            payload["category"] = category
        if confidence is not None:
            payload["confidence"] = confidence
        if flagged_content is not None:
            payload["flagged_content"] = flagged_content[:200]
        super().__init__(message, code=self.default_code, details=payload)


def normalize_exception(
    exc: Exception,
    *,
    function_name: Optional[str] = None,
) -> NoesisError:
    if isinstance(exc, NoesisError):
        return exc

    details: dict[str, Any] = {"exception_type": type(exc).__name__}
    if function_name is not None:
        details["function"] = function_name

    if isinstance(exc, asyncio.TimeoutError):
        return TimeoutExceededError(
            "Operation timed out",
            timeout_seconds=0.0,
            operation=function_name,
            details=details,
        )
    if isinstance(exc, (ConnectionError, OSError)):
        return APIClientError(
            str(exc),
            service="unknown",
            retryable=True,
            details=details,
        )
    if isinstance(exc, ValueError):
        return ValidationError(str(exc), details=details)

    return NoesisError(
        f"Unexpected error: {exc}",
        code="UNEXPECTED_ERROR",
        details=details,
    )


def handle_noesis_error(func: Callable[P, T]) -> Callable[P, T]:
    logger = logging.getLogger(func.__module__)

    if inspect.iscoroutinefunction(func):

        @wraps(func)
        async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> Any:
            try:
                return await func(*args, **kwargs)
            except NoesisError:
                raise
            except Exception as exc:
                logger.exception(
                    "Unhandled exception in %s",
                    func.__qualname__,
                    extra={
                        "function": func.__qualname__,
                        "exception_type": type(exc).__name__,
                    },
                )
                raise normalize_exception(exc, function_name=func.__qualname__) from exc

        return async_wrapper

    @wraps(func)
    def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> Any:
        try:
            return func(*args, **kwargs)
        except NoesisError:
            raise
        except Exception as exc:
            logger.exception(
                "Unhandled exception in %s",
                func.__qualname__,
                extra={
                    "function": func.__qualname__,
                    "exception_type": type(exc).__name__,
                },
            )
            raise normalize_exception(exc, function_name=func.__qualname__) from exc

    return sync_wrapper
