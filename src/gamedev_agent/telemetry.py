"""Structured JSONL audit and usage telemetry."""

from __future__ import annotations

import json
import os
import uuid
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .storage import FileLock, StateError


def _now() -> str:
    return datetime.now(UTC).isoformat()


class JsonlLog:
    """Append records under a cooperative lock and force them to disk."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def append(self, record: Mapping[str, Any]) -> dict[str, Any]:
        value = {"timestamp": _now(), "event_id": str(uuid.uuid4()), **record}
        serialized = json.dumps(value, sort_keys=True, ensure_ascii=False) + "\n"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with FileLock(self.path), self.path.open("a", encoding="utf-8") as stream:
            stream.write(serialized)
            stream.flush()
            os.fsync(stream.fileno())
        return value

    def read_all(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        records: list[dict[str, Any]] = []
        for number, line in enumerate(self.path.read_text(encoding="utf-8").splitlines(), 1):
            try:
                value = json.loads(line)
            except json.JSONDecodeError as error:
                raise StateError(f"invalid JSONL at {self.path}:{number}") from error
            if not isinstance(value, dict):
                raise StateError(f"expected JSON object at {self.path}:{number}")
            records.append(value)
        return records


class AuditLogger:
    def __init__(self, root: Path) -> None:
        self.log = JsonlLog(root / "logs" / "audit.jsonl")

    def record(
        self,
        *,
        event: str,
        actor: str,
        session_id: str | None = None,
        tool: str | None = None,
        outcome: str = "success",
        details: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self.log.append(
            {
                "event": event,
                "actor": actor,
                "session_id": session_id,
                "tool": tool,
                "outcome": outcome,
                "details": dict(details or {}),
            }
        )


class UsageTracker:
    def __init__(self, root: Path) -> None:
        self.log = JsonlLog(root / "logs" / "usage.jsonl")

    def record(
        self,
        *,
        agent: str,
        turns: int,
        cost_usd: float,
        session_id: str | None,
        model: str | None = None,
    ) -> dict[str, Any]:
        if turns < 0 or cost_usd < 0:
            raise StateError("usage values must be non-negative")
        return self.log.append(
            {
                "event": "result-message",
                "agent": agent,
                "turns": turns,
                "cost_usd": round(cost_usd, 8),
                "session_id": session_id,
                "model": model,
            }
        )

    def summary(self) -> dict[str, Any]:
        records = self.log.read_all()
        by_agent: dict[str, dict[str, float | int]] = {}
        for record in records:
            agent = str(record.get("agent", "unknown"))
            bucket = by_agent.setdefault(agent, {"results": 0, "turns": 0, "cost_usd": 0.0})
            bucket["results"] = int(bucket["results"]) + 1
            bucket["turns"] = int(bucket["turns"]) + int(record.get("turns", 0))
            bucket["cost_usd"] = round(
                float(bucket["cost_usd"]) + float(record.get("cost_usd", 0.0)), 8
            )
        return {"results": len(records), "by_agent": by_agent}
