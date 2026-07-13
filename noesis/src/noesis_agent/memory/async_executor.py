from __future__ import annotations

import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from typing import Any, Callable


class MemoryQueueFull(RuntimeError):
    pass


class AsyncMemoryExecutor:
    """Dedicated bounded SQLite executor; never uses asyncio's unbounded default pool."""

    def __init__(self, *, queue_size: int, worker_count: int) -> None:
        self.queue_size = max(1, min(queue_size, 4096))
        self.worker_count = max(1, min(worker_count, 8))
        self._capacity = threading.BoundedSemaphore(self.queue_size + self.worker_count)
        self._executor = ThreadPoolExecutor(max_workers=self.worker_count,
                                            thread_name_prefix="noesis-memory")
        self._lock = threading.Lock()
        self._submitted = 0
        self._running = 0
        self._closed = False

    async def run(self, func: Callable[..., Any], *args: Any, timeout: float, **kwargs: Any) -> Any:
        if self._closed:
            raise RuntimeError("memory_executor_closed")
        if not self._capacity.acquire(blocking=False):
            raise MemoryQueueFull("memory_queue_full")
        with self._lock:
            self._submitted += 1

        def invoke() -> Any:
            with self._lock:
                self._running += 1
            try:
                return func(*args, **kwargs)
            finally:
                with self._lock:
                    self._running -= 1
                    self._submitted -= 1
                self._capacity.release()

        future = asyncio.get_running_loop().run_in_executor(self._executor, partial(invoke))
        try:
            return await asyncio.wait_for(asyncio.shield(future), timeout=timeout)
        except asyncio.CancelledError:
            future.cancel()
            raise

    async def shutdown(self) -> None:
        if self._closed:
            return
        self._closed = True
        await asyncio.to_thread(self._executor.shutdown, wait=True, cancel_futures=True)

    def health(self) -> dict[str, Any]:
        with self._lock:
            submitted, running = self._submitted, self._running
        return {"state": "stopped" if self._closed else "ready", "queue_capacity": self.queue_size,
                "queue_depth": max(0, submitted - running), "in_flight": running,
                "workers": self.worker_count, "accepting_work": not self._closed}


__all__ = ["AsyncMemoryExecutor", "MemoryQueueFull"]
