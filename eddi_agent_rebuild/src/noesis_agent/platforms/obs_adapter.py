from __future__ import annotations

import json
import websockets


class OBSAdapter:
    """Minimal OBS WebSocket controller (expects OBS WebSocket v5)."""

    def __init__(self, url: str = "ws://localhost:4455", password: str | None = None) -> None:
        self.url = url
        self.password = password

    async def _send(self, payload: dict) -> None:
        async with websockets.connect(self.url) as ws:
            await ws.send(json.dumps(payload))

    async def start_recording(self) -> None:
        await self._send({"op": 6, "d": {"requestType": "StartRecord", "requestId": "start-record"}})

    async def stop_recording(self) -> None:
        await self._send({"op": 6, "d": {"requestType": "StopRecord", "requestId": "stop-record"}})
