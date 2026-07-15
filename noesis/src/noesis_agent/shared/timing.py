from __future__ import annotations

import asyncio
import logging
import statistics
import time
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass, field
from functools import wraps
from typing import Any, Callable, Iterator, AsyncIterator, ParamSpec, TypeVar, Optional

P = ParamSpec("P")
T = TypeVar("T")


@dataclass(slots=True)
class Timer:
    start_time: Optional[float] = None
    end_time: Optional[float] = None

    def start(self) -> Timer:
        self.start_time = time.perf_counter()
        self.end_time = None
        return self

    def stop(self) -> Timer:
        if self.start_time is None:
            raise RuntimeError("Timer has not been started")
        self.end_time = time.perf_counter()
        return self

    def reset(self) -> Timer:
        self.start_time = None
        self.end_time = None
        return self

    @property
    def is_running(self) -> bool:
        return self.start_time is not None and self.end_time is None

    @property
    def elapsed(self) -> float:
        if self.start_time is None:
            return 0.0
        end = self.end_time if self.end_time is not None else time.perf_counter()
        return end - self.start_time

    @property
    def elapsed_ms(self) -> float:
        return self.elapsed * 1000.0


@dataclass(slots=True)
class PerformanceSample:
    elapsed_ms: float
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class PerformanceTracker:
    name: str
    samples: list[PerformanceSample] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @contextmanager
    def track(self, **sample_metadata: Any) -> Iterator[Timer]:
        timer = Timer().start()
        try:
            yield timer
        finally:
            timer.stop()
            self.samples.append(
                PerformanceSample(
                    elapsed_ms=timer.elapsed_ms,
                    metadata=dict(sample_metadata),
                )
            )

    @asynccontextmanager
    async def atrack(self, **sample_metadata: Any) -> AsyncIterator[Timer]:
        timer = Timer().start()
        try:
            yield timer
        finally:
            timer.stop()
            self.samples.append(
                PerformanceSample(
                    elapsed_ms=timer.elapsed_ms,
                    metadata=dict(sample_metadata),
                )
            )

    def add_sample(self, elapsed_ms: float, **sample_metadata: Any) -> None:
        if elapsed_ms < 0:
            raise ValueError("elapsed_ms cannot be negative")
        self.samples.append(
            PerformanceSample(
                elapsed_ms=float(elapsed_ms),
                metadata=dict(sample_metadata),
            )
        )

    def clear(self) -> None:
        self.samples.clear()

    def summary(self) -> dict[str, Any]:
        if not self.samples:
            return {
                "name": self.name,
                "count": 0,
                "min_ms": 0.0,
                "max_ms": 0.0,
                "avg_ms": 0.0,
                "median_ms": 0.0,
                "p95_ms": 0.0,
                "total_ms": 0.0,
                "metadata": dict(self.metadata),
            }

        values = [sample.elapsed_ms for sample in self.samples]
        sorted_values = sorted(values)
        index_95 = max(0, min(len(sorted_values) - 1, int(round(0.95 * (len(sorted_values) - 1)))))

        return {
            "name": self.name,
            "count": len(values),
            "min_ms": round(min(values), 4),
            "max_ms": round(max(values), 4),
            "avg_ms": round(sum(values) / len(values), 4),
            "median_ms": round(statistics.median(values), 4),
            "p95_ms": round(sorted_values[index_95], 4),
            "total_ms": round(sum(values), 4),
            "metadata": dict(self.metadata),
        }


class TimerUtil:
    @staticmethod
    @contextmanager
    def measure(
        name: str,
        logger: Optional[logging.Logger] = None,
        *,
        level: int = logging.DEBUG,
        extra: Optional[dict[str, Any]] = None,
    ) -> Iterator[Timer]:
        timer = Timer().start()
        try:
            yield timer
        finally:
            timer.stop()
            if logger is not None:
                payload = {"operation": name, "elapsed_ms": round(timer.elapsed_ms, 2)}
                if extra:
                    payload.update(extra)
                logger.log(level, f"{name} completed", extra=payload)

    @staticmethod
    @asynccontextmanager
    async def ameasure(
        name: str,
        logger: Optional[logging.Logger] = None,
        *,
        level: int = logging.DEBUG,
        extra: Optional[dict[str, Any]] = None,
    ) -> AsyncIterator[Timer]:
        timer = Timer().start()
        try:
            yield timer
        finally:
            timer.stop()
            if logger is not None:
                payload = {"operation": name, "elapsed_ms": round(timer.elapsed_ms, 2)}
                if extra:
                    payload.update(extra)
                logger.log(level, f"{name} completed", extra=payload)

    @staticmethod
    def decorate(
        *,
        logger: Optional[logging.Logger] = None,
        level: int = logging.DEBUG,
        include_args: bool = False,
        arg_max_length: int = 250,
    ) -> Callable[[Callable[P, T]], Callable[P, T]]:
        def decorator(func: Callable[P, T]) -> Callable[P, T]:
            function_name = func.__qualname__
            active_logger = logger or logging.getLogger(func.__module__)

            if asyncio.iscoroutinefunction(func):
                @wraps(func)
                async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> Any:
                    timer = Timer().start()
                    try:
                        return await func(*args, **kwargs)
                    finally:
                        timer.stop()
                        extra: dict[str, Any] = {
                            "function": function_name,
                            "elapsed_ms": round(timer.elapsed_ms, 2),
                        }
                        if include_args:
                            extra["args"] = repr(args)[:arg_max_length]
                            extra["kwargs"] = repr(kwargs)[:arg_max_length]
                        active_logger.log(level, f"{function_name} timed", extra=extra)

                return async_wrapper

            @wraps(func)
            def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> Any:
                timer = Timer().start()
                try:
                    return func(*args, **kwargs)
                finally:
                    timer.stop()
                    extra: dict[str, Any] = {
                        "function": function_name,
                        "elapsed_ms": round(timer.elapsed_ms, 2),
                    }
                    if include_args:
                        extra["args"] = repr(args)[:arg_max_length]
                        extra["kwargs"] = repr(kwargs)[:arg_max_length]
                    active_logger.log(level, f"{function_name} timed", extra=extra)

            return sync_wrapper

        return decorator


measure_time = TimerUtil.measure
ameasure_time = TimerUtil.ameasure
timed = TimerUtil.decorate


__all__ = [
    "PerformanceSample",
    "PerformanceTracker",
    "Timer",
    "TimerUtil",
    "ameasure_time",
    "measure_time",
    "timed",
]
