from __future__ import annotations

import asyncio
import sounddevice as sd


class MicrophoneInputStream:
    """Captures microphone audio and yields PCM chunks."""

    def __init__(self, samplerate: int = 16000, blocksize: int = 2048) -> None:
        self.samplerate = samplerate
        self.blocksize = blocksize

    async def stream(self):
        loop = asyncio.get_event_loop()
        q: asyncio.Queue[bytes] = asyncio.Queue()

        def _callback(indata, frames, time, status):
            loop.call_soon_threadsafe(q.put_nowait, bytes(indata))

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
