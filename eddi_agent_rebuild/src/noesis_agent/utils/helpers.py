from __future__ import annotations

from typing import Any, Iterable, Mapping, TypeVar, Optional
from pathlib import Path
import os
import shutil

T = TypeVar("T")


class FileSystem:
    @staticmethod
    def ensure_dir(path: str | Path) -> Path:
        target = Path(path).resolve()
        target.mkdir(parents=True, exist_ok=True)
        if not os.access(target, os.W_OK):
            raise PermissionError(f"Directory not writable: {target}")
        return target

    @staticmethod
    def clear_dir(path: str | Path) -> None:
        target = Path(path)
        if not target.exists():
            return
        for item in target.iterdir():
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()

    @staticmethod
    def safe_delete(path: str | Path) -> bool:
        target = Path(path)
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

    @staticmethod
    def atomic_write(path: str | Path, content: str | bytes, encoding: str = "utf-8") -> None:
        target = Path(path)
        temp_path = target.with_suffix(target.suffix + ".tmp")
        try:
            if isinstance(content, str):
                temp_path.write_text(content, encoding=encoding)
            else:
                temp_path.write_bytes(content)
            temp_path.replace(target)
        finally:
            if temp_path.exists():
                temp_path.unlink(missing_ok=True)