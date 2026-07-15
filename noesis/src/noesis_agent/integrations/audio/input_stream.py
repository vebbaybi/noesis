from __future__ import annotations

import asyncio


class MicrophoneInputStream:
    """Captures microphone audio and yields PCM chunks."""

    def __init__(self, samplerate: int = 16000, blocksize: int = 2048) -> None:
        self.samplerate = samplerate
        self.blocksize = blocksize

    async def stream(self):
        try:
            import sounddevice as sd
        except ImportError as exc:  # pragma: no cover - optional dependency path
            raise RuntimeError('Microphone capture requires the "audio" extra') from exc
        loop = asyncio.get_running_loop()
        q: asyncio.Queue[bytes] = asyncio.Queue(maxsize=32)

        def _callback(indata, frames, time, status):
            def _enqueue() -> None:
                if not q.full():
                    q.put_nowait(bytes(indata))
            loop.call_soon_threadsafe(_enqueue)

        with sd.RawInputStream(
            samplerate=self.samplerate,
            blocksize=self.blocksize,
            channels=1,
            dtype="int16",
            callback=_callback,
        ):
            while True:
                chunk = await q.get()
                yield chunk
