"""Human approval records and cross-client pre-tool safety classification."""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

from .storage import JsonObject, JsonStore, StateError


@dataclass(frozen=True)
class DestructiveOperation:
    operation: str
    resource: str
    reason: str


class ApprovalStore:
    """Issue and consume narrow, expiring, one-time approvals."""

    def __init__(self, root: Path) -> None:
        self.store = JsonStore(root.resolve() / "state" / "approvals.json")

    def issue(
        self, *, operation: str, resource: str, actor: str, ttl_minutes: int = 15
    ) -> JsonObject:
        if not operation or not resource or not actor:
            raise StateError("operation, resource, and actor are required")
        if not 1 <= ttl_minutes <= 60:
            raise StateError("approval ttl must be between 1 and 60 minutes")
        now = datetime.now(UTC)
        approval: JsonObject = {
            "id": str(uuid.uuid4()),
            "operation": operation,
            "resource": resource,
            "actor": actor,
            "created_at": now.isoformat(),
            "expires_at": (now + timedelta(minutes=ttl_minutes)).isoformat(),
            "consumed_at": None,
        }

        def append(value: JsonObject) -> None:
            value.setdefault("schema_version", 1)
            value.setdefault("approvals", []).append(approval)

        self.store.update(append, lambda: {"schema_version": 1, "approvals": []})
        return approval

    def consume(self, operation: str, resource: str) -> JsonObject | None:
        now = datetime.now(UTC)

        def find(value: JsonObject) -> JsonObject | None:
            for approval in reversed(value.get("approvals", [])):
                if approval.get("consumed_at") is not None:
                    continue
                if approval.get("operation") != operation or approval.get("resource") != resource:
                    continue
                expires_at = datetime.fromisoformat(str(approval["expires_at"]))
                if expires_at <= now:
                    continue
                approval["consumed_at"] = now.isoformat()
                return cast(JsonObject, approval)
            return None

        return self.store.update(find, lambda: {"schema_version": 1, "approvals": []})


_FORCE_PUSH = re.compile(r"(?:^|\s)git\s+push\b[^\n]*(?:--force(?:-with-lease)?|-f)(?:\s|$)", re.I)
_DESTRUCTIVE_GIT = re.compile(
    r"(?:^|\s)git\s+(?:reset\s+--hard|clean\s+-[^\n]*f|branch\s+-D)(?:\s|$)", re.I
)
_DELETE_WORD = re.compile(r"(?:delete|remove|destroy)(?:_|-|\b)", re.I)
_EXPORT_WORD = re.compile(r"(?:export|save)(?:_|-|\b)", re.I)


def classify_event(event: dict[str, Any]) -> DestructiveOperation | None:
    tool_name = str(event.get("tool_name", ""))
    tool_input = event.get("tool_input")
    if not isinstance(tool_input, dict):
        tool_input = {}
    command = str(tool_input.get("command", ""))
    if tool_name.lower() in {"shell", "execute_bash", "bash"}:
        if _FORCE_PUSH.search(command):
            return DestructiveOperation(
                "git.force-push", command, "force-push can rewrite shared history"
            )
        if _DESTRUCTIVE_GIT.search(command):
            return DestructiveOperation(
                "git.destructive", command, "the Git command can discard work"
            )
    lowered_tool = tool_name.lower()
    serialized = json.dumps(tool_input, sort_keys=True, default=str)
    resource = _resource(tool_name, tool_input)
    if "blender" in lowered_tool and _DELETE_WORD.search(lowered_tool):
        return DestructiveOperation(
            "blender.delete", resource, "deleting scene data may be irreversible"
        )
    if "unity" in lowered_tool and _DELETE_WORD.search(lowered_tool):
        return DestructiveOperation(
            "unity.delete", resource, "deleting scene or asset data may be irreversible"
        )
    overwrite = bool(tool_input.get("overwrite") or tool_input.get("force"))
    if overwrite and _EXPORT_WORD.search(lowered_tool + " " + serialized):
        return DestructiveOperation(
            "export.overwrite", resource, "overwriting an export can destroy the prior artifact"
        )
    return None


def _resource(tool_name: str, tool_input: dict[str, Any]) -> str:
    for key in ("path", "file", "filepath", "object", "object_name", "asset", "name"):
        value = tool_input.get(key)
        if value:
            return str(value)
    return tool_name


def evaluate_event(root: Path, event: dict[str, Any]) -> tuple[bool, str]:
    operation = classify_event(event)
    if operation is None:
        return True, "operation is not classified as destructive"
    approval = ApprovalStore(root).consume(operation.operation, operation.resource)
    if approval is not None:
        return True, f"consumed approval {approval['id']}"
    message = (
        f"Blocked {operation.operation} for {operation.resource}: {operation.reason}. "
        f"Run `gamedev approve --operation {operation.operation} "
        f"--resource {json.dumps(operation.resource)} --actor <name>` and retry."
    )
    return False, message
