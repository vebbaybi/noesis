"""
Structured logging module for the NOESIS agent.
Provides structured logging, context propagation, async logging, performance tracking,
rate limiting, redaction, rotating file handlers, and optional webhook alerts.
"""

from __future__ import annotations

import asyncio
import contextvars
import json
import logging
import logging.handlers
import queue
import re
import sys
import threading
import time
import urllib.error
import urllib.request
from contextlib import suppress
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, MutableMapping, ParamSpec, TypeVar


P = ParamSpec("P")
T = TypeVar("T")


AUDIT_LEVEL = 25
METRICS_LEVEL = 35

logging.addLevelName(AUDIT_LEVEL, "AUDIT")
logging.addLevelName(METRICS_LEVEL, "METRICS")


_trace_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar("noesis_trace_id", default=None)
_session_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar("noesis_session_id", default=None)
_room_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar("noesis_room_id", default=None)
_speaker_var: contextvars.ContextVar[str | None] = contextvars.ContextVar("noesis_speaker", default=None)


_STANDARD_LOG_RECORD_FIELDS = {
    "args",
    "asctime",
    "created",
    "exc_info",
    "exc_text",
    "filename",
    "funcName",
    "levelname",
    "levelno",
    "lineno",
    "module",
    "msecs",
    "message",
    "msg",
    "name",
    "pathname",
    "process",
    "processName",
    "relativeCreated",
    "stack_info",
    "thread",
    "threadName",
    "taskName",
}


def sanitize_log_extra(extra: Mapping[str, Any] | None) -> dict[str, Any]:
    """Namespace keys that Python logging reserves for LogRecord attributes."""
    if not extra:
        return {}
    sanitized: dict[str, Any] = {}
    for key, value in extra.items():
        safe_key = f"extra_{key}" if key in _STANDARD_LOG_RECORD_FIELDS else key
        while safe_key in _STANDARD_LOG_RECORD_FIELDS or safe_key in sanitized:
            safe_key = f"extra_{safe_key}"
        sanitized[safe_key] = value
    return sanitized


SENSITIVE_PATTERNS: tuple[tuple[str, str, int], ...] = (
    (r"(?i)(api[_-]?key\s*[=:]\s*[\"']?)([^\"'\s,&]+)", r"\1***REDACTED***", 0),
    (r"(?i)(authorization\s*:\s*bearer\s+)([a-z0-9\-._~+/=]+)", r"\1***REDACTED***", 0),
    (r"(?i)(bearer\s+)([a-z0-9\-._~+/=]+)", r"\1***REDACTED***", 0),
    (r"(?i)(token\s*[=:]\s*[\"']?)([^\"'\s,&]+)", r"\1***REDACTED***", 0),
    (r"(?i)(secret\s*[=:]\s*[\"']?)([^\"'\s,&]+)", r"\1***REDACTED***", 0),
    (r"(?i)(password\s*[=:]\s*[\"']?)([^\"'\s,&]+)", r"\1***REDACTED***", 0),
    (r"\b[\w.+-]+@[\w.-]+\.\w+\b", "***EMAIL***", 0),
    (r"\b(?:\d[ -]*?){13,19}\b", "***CARD***", 0),
)


def redact_sensitive_data(value: Any) -> Any:
    if isinstance(value, str):
        redacted = value
        for pattern, replacement, flags in SENSITIVE_PATTERNS:
            redacted = re.sub(pattern, replacement, redacted, flags=flags)
        return redacted

    if isinstance(value, Mapping):
        return {str(k): redact_sensitive_data(v) for k, v in value.items()}

    if isinstance(value, (list, tuple, set)):
        return [redact_sensitive_data(v) for v in value]

    return value


def _safe_json_default(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc).isoformat()
        return value.isoformat()
    return repr(value)


class CustomLogger(logging.Logger):
    def audit(self, msg: str, *args: Any, **kwargs: Any) -> None:
        if self.isEnabledFor(AUDIT_LEVEL):
            self._log(AUDIT_LEVEL, msg, args, **kwargs)

    def metrics(self, msg: str, *args: Any, **kwargs: Any) -> None:
        if self.isEnabledFor(METRICS_LEVEL):
            self._log(METRICS_LEVEL, msg, args, **kwargs)


logging.setLoggerClass(CustomLogger)


class ContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        trace_id = _trace_id_var.get()
        session_id = _session_id_var.get()
        room_id = _room_id_var.get()
        speaker = _speaker_var.get()

        if not hasattr(record, "trace_id") and trace_id is not None:
            record.trace_id = trace_id
        if not hasattr(record, "session_id") and session_id is not None:
            record.session_id = session_id
        if not hasattr(record, "room_id") and room_id is not None:
            record.room_id = room_id
        if not hasattr(record, "speaker") and speaker is not None:
            record.speaker = speaker

        return True


class RateLimitingFilter(logging.Filter):
    def __init__(self, rate: int = 10, per_seconds: int = 60) -> None:
        super().__init__()
        if rate <= 0:
            raise ValueError("rate must be greater than 0")
        if per_seconds <= 0:
            raise ValueError("per_seconds must be greater than 0")

        self.rate = rate
        self.per_seconds = per_seconds
        self._events: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def filter(self, record: logging.LogRecord) -> bool:
        key = f"{record.name}:{record.levelno}:{record.getMessage()}"
        now = time.monotonic()

        with self._lock:
            timestamps = self._events.get(key, [])
            cutoff = now - self.per_seconds
            timestamps = [ts for ts in timestamps if ts >= cutoff]

            if len(timestamps) < self.rate:
                timestamps.append(now)
                self._events[key] = timestamps
                return True

            self._events[key] = timestamps
            return False


class StructuredJSONFormatter(logging.Formatter):
    def __init__(self, include_extra: bool = True) -> None:
        super().__init__()
        self.include_extra = include_extra

    def format(self, record: logging.LogRecord) -> str:
        message = redact_sensitive_data(record.getMessage())

        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "message": message,
            "process": record.process,
            "thread": record.threadName,
        }

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        if record.stack_info:
            payload["stack"] = self.formatStack(record.stack_info)

        if hasattr(record, "trace_id"):
            payload["trace_id"] = redact_sensitive_data(record.trace_id)
        if hasattr(record, "session_id"):
            payload["session_id"] = redact_sensitive_data(record.session_id)
        if hasattr(record, "room_id"):
            payload["room_id"] = redact_sensitive_data(record.room_id)
        if hasattr(record, "speaker"):
            payload["speaker"] = redact_sensitive_data(record.speaker)

        if self.include_extra:
            extras = {
                key: redact_sensitive_data(value)
                for key, value in record.__dict__.items()
                if key not in _STANDARD_LOG_RECORD_FIELDS and not key.startswith("_")
            }
            if extras:
                payload["extra"] = extras

        return json.dumps(payload, ensure_ascii=False, default=_safe_json_default)


class ColoredConsoleFormatter(logging.Formatter):
    RESET = "\033[0m"
    COLORS = {
        "DEBUG": "\033[36m",
        "INFO": "\033[32m",
        "AUDIT": "\033[35m",
        "WARNING": "\033[33m",
        "METRICS": "\033[34m",
        "ERROR": "\033[31m",
        "CRITICAL": "\033[41m",
    }

    def __init__(
        self,
        fmt: str,
        datefmt: str,
        use_color: bool = True,
    ) -> None:
        super().__init__(fmt=fmt, datefmt=datefmt)
        self.use_color = use_color and sys.stdout.isatty()

    def format(self, record: logging.LogRecord) -> str:
        original_levelname = record.levelname
        original_msg = record.msg

        try:
            if self.use_color:
                color = self.COLORS.get(record.levelname, self.RESET)
                record.levelname = f"{color}{record.levelname}{self.RESET}"
            record.msg = redact_sensitive_data(record.getMessage())
            record.args = ()
            return super().format(record)
        finally:
            record.levelname = original_levelname
            record.msg = original_msg


class ContextAdapter(logging.LoggerAdapter):
    def process(self, msg: str, kwargs: MutableMapping[str, Any]) -> tuple[str, MutableMapping[str, Any]]:
        extra = dict(kwargs.get("extra") or {})
        extra.update(self.extra)
        kwargs["extra"] = sanitize_log_extra(extra)
        return msg, kwargs

    def with_context(self, **context: Any) -> "ContextAdapter":
        merged = dict(self.extra)
        merged.update(context)
        return ContextAdapter(self.logger, merged)


class WebhookAlertHandler(logging.Handler):
    def __init__(
        self,
        webhook_url: str,
        min_level: int = logging.ERROR,
        timeout_seconds: float = 5.0,
        cooldown_seconds: float = 300.0,
    ) -> None:
        super().__init__(level=min_level)
        self.webhook_url = webhook_url
        self.timeout_seconds = timeout_seconds
        self.cooldown_seconds = cooldown_seconds
        self._last_sent: dict[str, float] = {}
        self._lock = threading.Lock()

    def emit(self, record: logging.LogRecord) -> None:
        if record.levelno < self.level:
            return

        key = f"{record.name}:{record.levelname}:{record.getMessage()}"
        now = time.monotonic()

        with self._lock:
            last = self._last_sent.get(key)
            if last is not None and (now - last) < self.cooldown_seconds:
                return
            self._last_sent[key] = now

        payload = {
            "service": record.name,
            "level": record.levelname,
            "message": redact_sensitive_data(record.getMessage()),
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "trace_id": getattr(record, "trace_id", None),
            "session_id": getattr(record, "session_id", None),
            "room_id": getattr(record, "room_id", None),
            "speaker": getattr(record, "speaker", None),
        }

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            self.webhook_url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds):
                return
        except urllib.error.URLError:
            self.handleError(record)


class AsyncLogger:
    def __init__(self, logger_name: str | None = None, max_queue_size: int = 10000) -> None:
        self.logger = logging.getLogger(logger_name) if logger_name else logging.getLogger()
        self._queue: asyncio.Queue[tuple[int, str, dict[str, Any]]] = asyncio.Queue(maxsize=max_queue_size)
        self._consumer_task: asyncio.Task[None] | None = None
        self._running = False

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._consumer_task = asyncio.create_task(self._consumer(), name="noesis-async-logger")

    async def stop(self) -> None:
        self._running = False
        if self._consumer_task is not None:
            self._consumer_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._consumer_task
            self._consumer_task = None
        await self._drain_queue()

    async def _consumer(self) -> None:
        while self._running:
            try:
                level, message, kwargs = await asyncio.wait_for(self._queue.get(), timeout=0.5)
            except asyncio.TimeoutError:
                continue
            self.logger.log(level, message, **kwargs)

    async def _drain_queue(self) -> None:
        while True:
            try:
                level, message, kwargs = self._queue.get_nowait()
            except asyncio.QueueEmpty:
                break
            self.logger.log(level, message, **kwargs)

    async def log(self, level: int, message: str, **kwargs: Any) -> None:
        try:
            self._queue.put_nowait((level, message, kwargs))
        except asyncio.QueueFull:
            self.logger.log(level, message, **kwargs)

    async def debug(self, message: str, **kwargs: Any) -> None:
        await self.log(logging.DEBUG, message, **kwargs)

    async def info(self, message: str, **kwargs: Any) -> None:
        await self.log(logging.INFO, message, **kwargs)

    async def audit(self, message: str, **kwargs: Any) -> None:
        await self.log(AUDIT_LEVEL, message, **kwargs)

    async def warning(self, message: str, **kwargs: Any) -> None:
        await self.log(logging.WARNING, message, **kwargs)

    async def metrics(self, message: str, **kwargs: Any) -> None:
        await self.log(METRICS_LEVEL, message, **kwargs)

    async def error(self, message: str, **kwargs: Any) -> None:
        await self.log(logging.ERROR, message, **kwargs)

    async def critical(self, message: str, **kwargs: Any) -> None:
        await self.log(logging.CRITICAL, message, **kwargs)


class SessionLogger:
    def __init__(self, logger: logging.Logger) -> None:
        self.logger = logger

    def set_session(self, session_id: str, room_id: str | None = None) -> ContextAdapter:
        context: dict[str, Any] = {"session_id": session_id}
        if room_id is not None:
            context["room_id"] = room_id
        return ContextAdapter(self.logger, context)

    def log_transcript(
        self,
        *,
        session_id: str,
        speaker: str,
        text: str,
        room_id: str | None = None,
        trace_id: str | None = None,
        **extra: Any,
    ) -> None:
        payload: dict[str, Any] = {
            "session_id": session_id,
            "speaker": speaker,
            "message_length": len(text),
            "message_preview": text[:250],
            "type": "transcript",
        }
        if room_id is not None:
            payload["room_id"] = room_id
        if trace_id is not None:
            payload["trace_id"] = trace_id
        payload.update(extra)
        self.logger.info("Transcript entry", extra=sanitize_log_extra(payload))

    def log_llm_call(
        self,
        *,
        session_id: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        latency_ms: float,
        room_id: str | None = None,
        trace_id: str | None = None,
        **extra: Any,
    ) -> None:
        payload: dict[str, Any] = {
            "session_id": session_id,
            "model": model,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
            "latency_ms": round(latency_ms, 2),
            "type": "llm_metrics",
        }
        if room_id is not None:
            payload["room_id"] = room_id
        if trace_id is not None:
            payload["trace_id"] = trace_id
        payload.update(extra)
        self.logger.metrics("LLM API call", extra=sanitize_log_extra(payload))


def set_trace_id(trace_id: str | None) -> contextvars.Token[str | None]:
    return _trace_id_var.set(trace_id)


def reset_trace_id(token: contextvars.Token[str | None]) -> None:
    _trace_id_var.reset(token)


def set_session_context(
    *,
    session_id: str | None = None,
    room_id: str | None = None,
    speaker: str | None = None,
) -> dict[str, contextvars.Token[str | None]]:
    tokens: dict[str, contextvars.Token[str | None]] = {}
    if session_id is not None:
        tokens["session_id"] = _session_id_var.set(session_id)
    if room_id is not None:
        tokens["room_id"] = _room_id_var.set(room_id)
    if speaker is not None:
        tokens["speaker"] = _speaker_var.set(speaker)
    return tokens


def reset_session_context(tokens: Mapping[str, contextvars.Token[str | None]]) -> None:
    if "session_id" in tokens:
        _session_id_var.reset(tokens["session_id"])
    if "room_id" in tokens:
        _room_id_var.reset(tokens["room_id"])
    if "speaker" in tokens:
        _speaker_var.reset(tokens["speaker"])


def log_performance(
    *,
    level: int = logging.DEBUG,
    log_args: bool = False,
    arg_max_length: int = 250,
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        logger = logging.getLogger(func.__module__)

        if asyncio.iscoroutinefunction(func):
            @wraps(func)
            async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> Any:
                start = time.perf_counter()
                try:
                    result = await func(*args, **kwargs)
                    duration_ms = (time.perf_counter() - start) * 1000.0
                    extra: dict[str, Any] = {
                        "function": func.__qualname__,
                        "duration_ms": round(duration_ms, 2),
                        "success": True,
                    }
                    if log_args:
                        extra["call_args"] = repr(args)[:arg_max_length]
                        extra["kwargs"] = repr(kwargs)[:arg_max_length]
                    logger.log(level, f"{func.__qualname__} completed", extra=sanitize_log_extra(extra))
                    return result
                except Exception as exc:
                    duration_ms = (time.perf_counter() - start) * 1000.0
                    logger.error(
                        f"{func.__qualname__} failed",
                        exc_info=True,
                        extra={
                            "function": func.__qualname__,
                            "duration_ms": round(duration_ms, 2),
                            "success": False,
                            "error_type": type(exc).__name__,
                            "error": str(exc)[:500],
                        },
                    )
                    raise

            return async_wrapper

        @wraps(func)
        def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> Any:
            start = time.perf_counter()
            try:
                result = func(*args, **kwargs)
                duration_ms = (time.perf_counter() - start) * 1000.0
                extra: dict[str, Any] = {
                    "function": func.__qualname__,
                    "duration_ms": round(duration_ms, 2),
                    "success": True,
                }
                if log_args:
                    extra["call_args"] = repr(args)[:arg_max_length]
                    extra["kwargs"] = repr(kwargs)[:arg_max_length]
                logger.log(level, f"{func.__qualname__} completed", extra=sanitize_log_extra(extra))
                return result
            except Exception as exc:
                duration_ms = (time.perf_counter() - start) * 1000.0
                logger.error(
                    f"{func.__qualname__} failed",
                    exc_info=True,
                    extra={
                        "function": func.__qualname__,
                        "duration_ms": round(duration_ms, 2),
                        "success": False,
                        "error_type": type(exc).__name__,
                        "error": str(exc)[:500],
                    },
                )
                raise

        return sync_wrapper

    return decorator


def _remove_all_handlers(logger: logging.Logger) -> None:
    handlers = list(logger.handlers)
    for handler in handlers:
        logger.removeHandler(handler)
        with suppress(Exception):
            handler.flush()
        with suppress(Exception):
            handler.close()


def _build_handlers(
    *,
    log_dir: Path,
    service_name: str,
    env: str,
    enable_json: bool,
    enable_alerts: bool,
    alert_webhook: str | None,
    rate_limit: tuple[int, int] | None,
) -> list[logging.Handler]:
    log_dir.mkdir(parents=True, exist_ok=True)

    formatter_text = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    formatter_text_detailed = "%(asctime)s | %(levelname)s | %(name)s:%(lineno)d | %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"

    handlers: list[logging.Handler] = []

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(
        ColoredConsoleFormatter(
            fmt=formatter_text,
            datefmt=datefmt,
            use_color=env.lower() != "production",
        )
    )
    handlers.append(console)

    file_handler = logging.handlers.TimedRotatingFileHandler(
        filename=str(log_dir / f"{service_name}.log"),
        when="midnight",
        interval=1,
        backupCount=30,
        encoding="utf-8",
        utc=True,
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(logging.Formatter(fmt=formatter_text_detailed, datefmt=datefmt))
    handlers.append(file_handler)

    error_handler = logging.handlers.RotatingFileHandler(
        filename=str(log_dir / f"{service_name}_error.log"),
        maxBytes=10 * 1024 * 1024,
        backupCount=10,
        encoding="utf-8",
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(logging.Formatter(fmt=formatter_text_detailed, datefmt=datefmt))
    handlers.append(error_handler)

    metrics_handler = logging.handlers.TimedRotatingFileHandler(
        filename=str(log_dir / f"{service_name}_metrics.log"),
        when="midnight",
        interval=1,
        backupCount=30,
        encoding="utf-8",
        utc=True,
    )
    metrics_handler.setLevel(METRICS_LEVEL)
    metrics_handler.setFormatter(StructuredJSONFormatter(include_extra=True))
    handlers.append(metrics_handler)

    if enable_json:
        json_handler = logging.handlers.TimedRotatingFileHandler(
            filename=str(log_dir / f"{service_name}_json.log"),
            when="midnight",
            interval=1,
            backupCount=7,
            encoding="utf-8",
            utc=True,
        )
        json_handler.setLevel(logging.INFO)
        json_handler.setFormatter(StructuredJSONFormatter(include_extra=True))
        handlers.append(json_handler)

    if enable_alerts and alert_webhook:
        alert_handler = WebhookAlertHandler(
            webhook_url=alert_webhook,
            min_level=logging.ERROR,
        )
        alert_handler.setFormatter(StructuredJSONFormatter(include_extra=True))
        handlers.append(alert_handler)

    context_filter = ContextFilter()
    limiter = RateLimitingFilter(rate=rate_limit[0], per_seconds=rate_limit[1]) if rate_limit else None

    for handler in handlers:
        handler.addFilter(context_filter)
        if limiter is not None:
            handler.addFilter(limiter)

    return handlers


def configure_logging(
    *,
    level: str = "INFO",
    env: str = "development",
    service_name: str = "noesis_agent",
    log_dir: str | Path = "logs",
    enable_json: bool = False,
    enable_alerts: bool = False,
    alert_webhook: str | None = None,
    rate_limit: tuple[int, int] | None = None,
) -> logging.Logger:
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    root_logger = logging.getLogger()
    service_logger = logging.getLogger(service_name)

    _remove_all_handlers(root_logger)
    _remove_all_handlers(service_logger)

    root_logger.setLevel(numeric_level)
    service_logger.setLevel(numeric_level)

    handlers = _build_handlers(
        log_dir=Path(log_dir),
        service_name=service_name,
        env=env,
        enable_json=enable_json,
        enable_alerts=enable_alerts,
        alert_webhook=alert_webhook,
        rate_limit=rate_limit,
    )

    for handler in handlers:
        root_logger.addHandler(handler)

    service_logger.propagate = True

    def handle_exception(exc_type: type[BaseException], exc_value: BaseException, exc_traceback: Any) -> None:
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        logging.getLogger(service_name).critical(
            "Unhandled exception",
            exc_info=(exc_type, exc_value, exc_traceback),
        )

    sys.excepthook = handle_exception

    service_logger.info(
        "Logging configured",
        extra={
            "environment": env,
            "service_name": service_name,
            "log_level": level.upper(),
            "json_enabled": enable_json,
            "alerts_enabled": enable_alerts and bool(alert_webhook),
        },
    )

    return service_logger


def get_logger(name: str | None = None) -> logging.Logger:
    return logging.getLogger(name)


def get_context_logger(name: str | None = None, **context: Any) -> ContextAdapter:
    return ContextAdapter(get_logger(name), context)


def get_session_logger(name: str | None = None) -> SessionLogger:
    return SessionLogger(get_logger(name))


def get_async_logger(name: str | None = None) -> AsyncLogger:
    return AsyncLogger(name)


__all__ = [
    "AUDIT_LEVEL",
    "AsyncLogger",
    "ContextAdapter",
    "CustomLogger",
    "METRICS_LEVEL",
    "RateLimitingFilter",
    "SessionLogger",
    "StructuredJSONFormatter",
    "ColoredConsoleFormatter",
    "WebhookAlertHandler",
    "configure_logging",
    "get_async_logger",
    "get_context_logger",
    "get_logger",
    "get_session_logger",
    "log_performance",
    "redact_sensitive_data",
    "sanitize_log_extra",
    "reset_session_context",
    "reset_trace_id",
    "set_session_context",
    "set_trace_id",
]
