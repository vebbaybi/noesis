from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class JsonStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, namespace: str, key: str) -> Path:
        folder = self.root / namespace
        folder.mkdir(parents=True, exist_ok=True)
        return folder / f"{key}.json"

    def write(self, namespace: str, key: str, payload: dict[str, Any]) -> None:
        self._path(namespace, key).write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    def read(self, namespace: str, key: str) -> dict[str, Any] | None:
        path = self._path(namespace, key)
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def list_keys(self, namespace: str) -> list[str]:
        folder = self.root / namespace
        if not folder.exists():
            return []
        return sorted(p.stem for p in folder.glob("*.json"))

    def list(self, namespace: str) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        for key in self.list_keys(namespace):
            payload = self.read(namespace, key)
            if payload is not None:
                records.append(payload)
        return records
