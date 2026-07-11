from __future__ import annotations

import uuid


class Tracer:
    def start_span(self, name: str) -> dict:
        return {"trace_id": uuid.uuid4().hex, "name": name}
