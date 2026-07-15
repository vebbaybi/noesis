from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable, Iterable, List, TypeVar, Optional, Union

T = TypeVar("T")


class AsyncConcurrency:
    @staticmethod
    async def gather_limited(
        tasks: Iterable[Awaitable[T]],
        limit: int = 5,
        *,
        return_exceptions: bool = False,
    ) -> List[Union[T, BaseException]]:
        if limit <= 0:
            raise ValueError("limit must be greater than 0")
        semaphore = asyncio.Semaphore(limit)

        async def runner(coro: Awaitable[T]) -> T:
            async with semaphore:
                return await coro

        wrapped = [asyncio.create_task(runner(t)) for t in tasks]
        if not wrapped:
            return []
        try:
            return await asyncio.gather(*wrapped, return_exceptions=return_exceptions)
        except Exception:
            for task in wrapped:
                if not task.done():
                    task.cancel()
            raise

    @staticmethod
    async def run_with_timeout(
        coro: Awaitable[T],
        timeout: float,
        *,
        default: Optional[T] = None,
    ) -> T:
        try:
            return await asyncio.wait_for(coro, timeout=timeout)
        except asyncio.TimeoutError:
            if default is not None:
                return default
            raise

    @staticmethod
    async def batch_iterate(
        items: Iterable[T],
        handler: Callable[[T], Awaitable[Any]],
        batch_size: int = 10,
        *,
        delay_between_batches: float = 0.0,
    ) -> None:
        if batch_size <= 0:
            raise ValueError("batch_size must be greater than 0")
        batch: List[T] = []
        for item in items:
            batch.append(item)
            if len(batch) >= batch_size:
                await asyncio.gather(*(handler(i) for i in batch))
                batch.clear()
                if delay_between_batches > 0:
                    await asyncio.sleep(delay_between_batches)
        if batch:
            await asyncio.gather(*(handler(i) for i in batch))

    @staticmethod
    async def throttle(
        tasks: Iterable[Callable[[], Awaitable[T]]],
        max_per_second: float,
    ) -> List[T]:
        if max_per_second <= 0:
            raise ValueError("max_per_second must be greater than 0")
        results: List[T] = []
        interval = 1.0 / max_per_second
        for task in tasks:
            start = asyncio.get_event_loop().time()
            results.append(await task())
            elapsed = asyncio.get_event_loop().time() - start
            if elapsed < interval:
                await asyncio.sleep(interval - elapsed)
        return results
