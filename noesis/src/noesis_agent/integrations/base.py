from __future__ import annotations

import asyncio
from typing import Awaitable, Callable, Protocol


AudioCallback = Callable[[bytes, int, str | None], Awaitable[None]]


class PlatformAdapter(Protocol):
    async def join(self, *, session_id: str) -> None:
        ...

    async def leave(self) -> None:
        ...

    async def send_text(self, text: str) -> None:
        ...

    async def send_audio(self, audio_bytes: bytes, *, sample_rate: int = 24000) -> None:
        ...

    def register_audio_consumer(self, consumer: AudioCallback) -> None:
        ...
