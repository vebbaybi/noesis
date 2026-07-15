from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Union, Optional, List, Iterator


class NoesisFiles:
    def __init__(self, base_dir: Union[str, Path]) -> None:
        self.base_dir = Path(base_dir).resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def path(self, *parts: str) -> Path:
        return self.base_dir.joinpath(*parts)

    def ensure_dir(self, *parts: str) -> Path:
        target = self.path(*parts)
        target.mkdir(parents=True, exist_ok=True)
        if not os.access(target, os.W_OK):
            raise PermissionError(f"Directory not writable: {target}")
        return target

    def clear_dir(self, *parts: str) -> None:
        target = self.path(*parts)
        if not target.exists():
            return
        for item in target.iterdir():
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()

    def write_text(self, content: str, *parts: str, encoding: str = "utf-8") -> Path:
        target = self.path(*parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding=encoding)
        return target

    def read_text(self, *parts: str, encoding: str = "utf-8") -> str:
        return self.path(*parts).read_text(encoding=encoding)

    def write_bytes(self, content: bytes, *parts: str) -> Path:
        target = self.path(*parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        return target

    def read_bytes(self, *parts: str) -> bytes:
        return self.path(*parts).read_bytes()

    def exists(self, *parts: str) -> bool:
        return self.path(*parts).exists()

    def is_file(self, *parts: str) -> bool:
        return self.path(*parts).is_file()

    def is_dir(self, *parts: str) -> bool:
        return self.path(*parts).is_dir()

    def delete(self, *parts: str) -> bool:
        target = self.path(*parts)
        if not target.exists():
            return False
        try:
            if target.is_dir():
                shutil.rmtree(target)
            else:
                target.unlink()
            return True
        except (OSError, PermissionError):
            return False

    def list_dir(self, *parts: str, pattern: Optional[str] = None) -> List[Path]:
        target = self.path(*parts)
        if not target.exists() or not target.is_dir():
            return []
        if pattern:
            return list(target.glob(pattern))
        return list(target.iterdir())

    def walk(self, *parts: str) -> Iterator[Path]:
        target = self.path(*parts)
        if target.exists() and target.is_dir():
            yield from target.rglob("*")
