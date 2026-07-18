"""Pipeline loading and persistent stage coordination."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from .permissions import ApprovalStore
from .state import ManifestStore, SessionStore
from .storage import JsonObject, StateError


class PipelineCatalog:
    def __init__(self, root: Path) -> None:
        self.directory = root.resolve() / "pipelines"

    def names(self) -> list[str]:
        return sorted(path.stem for path in self.directory.glob("*.json"))

    def load(self, name: str) -> JsonObject:
        allowed = "abcdefghijklmnopqrstuvwxyz0123456789-"
        if not name or any(character not in allowed for character in name):
            raise StateError("invalid pipeline name")
        path = self.directory / f"{name}.json"
        if not path.exists():
            raise StateError(f"unknown pipeline: {name}")
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise StateError(f"invalid pipeline JSON: {path}") from error
        if not isinstance(value, dict) or value.get("name") != name:
            raise StateError(f"pipeline name does not match filename: {path}")
        stages = value.get("stages")
        if not isinstance(stages, list) or not stages:
            raise StateError(f"pipeline has no stages: {name}")
        ids = [stage.get("id") for stage in stages if isinstance(stage, dict)]
        if len(ids) != len(stages) or len(set(ids)) != len(ids):
            raise StateError(f"pipeline stage ids must be present and unique: {name}")
        return value


class PipelineCoordinator:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.catalog = PipelineCatalog(root)
        self.sessions = SessionStore(root)
        self.manifest = ManifestStore(root)
        self.approvals = ApprovalStore(root)

    def start(self, name: str) -> JsonObject:
        pipeline = self.catalog.load(name)
        stages: list[JsonObject] = [dict(stage) for stage in pipeline["stages"]]
        return self.sessions.start(name, stages)

    def resume(self, session_id: str | None = None) -> JsonObject:
        return self.sessions.read(session_id) if session_id else self.sessions.latest_active()

    def advance(self, session_id: str, actor: str) -> JsonObject:
        session = self.sessions.read(session_id)
        stage = session["stages"][session["current_stage"]]
        for gate in stage.get("completion_gates", []):
            if gate == "licenses-verified" and not self.manifest.all_licenses_verified():
                self.sessions.block(session_id, "not all asset licenses are verified")
                raise StateError("license gate failed: verify every asset license before advancing")
            if gate == "human-approval":
                resource = f"{session_id}:{stage['id']}"
                if self.approvals.consume("pipeline.stage", resource) is None:
                    self.sessions.block(session_id, f"approval required for stage {stage['id']}")
                    raise StateError(
                        "approval gate failed: run `gamedev approve --operation pipeline.stage "
                        f"--resource {resource} --actor <name>`"
                    )
        return self.sessions.advance(session_id, actor)


def current_stage(session: dict[str, Any]) -> dict[str, Any]:
    return cast(dict[str, Any], session["stages"][int(session["current_stage"])])
