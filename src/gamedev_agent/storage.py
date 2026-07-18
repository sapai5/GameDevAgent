"""Atomic JSON persistence with a portable cooperative lock."""

from __future__ import annotations

import json
import os
import tempfile
import time
from collections.abc import Callable
from contextlib import AbstractContextManager
from pathlib import Path
from types import TracebackType
from typing import Any, TypeVar

JsonObject = dict[str, Any]
T = TypeVar("T")


class StateError(RuntimeError):
    """Raised when persisted state is missing, corrupt, or cannot be locked."""


class FileLock(AbstractContextManager["FileLock"]):
    """A cross-platform lock based on exclusive lock-file creation."""

    def __init__(self, target: Path, timeout_seconds: float = 5.0) -> None:
        self.path = target.with_suffix(target.suffix + ".lock")
        self.timeout_seconds = timeout_seconds
        self._fd: int | None = None

    def __enter__(self) -> FileLock:
        deadline = time.monotonic() + self.timeout_seconds
        self.path.parent.mkdir(parents=True, exist_ok=True)
        while True:
            try:
                self._fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                os.write(self._fd, f"{os.getpid()}\n".encode())
                return self
            except FileExistsError as error:
                if time.monotonic() >= deadline:
                    raise StateError(f"timed out waiting for state lock: {self.path}") from error
                time.sleep(0.05)

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None
        self.path.unlink(missing_ok=True)


class JsonStore:
    """Read and atomically update one JSON object."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def read(self, default: Callable[[], JsonObject] | None = None) -> JsonObject:
        if not self.path.exists():
            if default is not None:
                return default()
            raise StateError(f"state file does not exist: {self.path}")
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise StateError(f"invalid JSON state in {self.path}: {error}") from error
        if not isinstance(value, dict):
            raise StateError(f"expected a JSON object in {self.path}")
        return value

    def write(self, value: JsonObject) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with FileLock(self.path):
            self._write_unlocked(value)

    def update(
        self,
        transform: Callable[[JsonObject], T],
        default: Callable[[], JsonObject] | None = None,
    ) -> T:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with FileLock(self.path):
            value = self.read(default)
            result = transform(value)
            self._write_unlocked(value)
            return result

    def _write_unlocked(self, value: JsonObject) -> None:
        serialized = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
        fd, temporary_name = tempfile.mkstemp(
            prefix=f".{self.path.name}.", suffix=".tmp", dir=self.path.parent
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                stream.write(serialized)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        finally:
            temporary.unlink(missing_ok=True)
