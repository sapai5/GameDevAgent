"""Deterministic evaluation cases for agent-package regressions."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .storage import StateError


class EvaluationRunner:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.cases_path = self.root / "evals" / "cases.json"

    def run(self, case_id: str | None = None) -> dict[str, Any]:
        cases = self._load_cases()
        if case_id:
            cases = [case for case in cases if case.get("id") == case_id]
            if not cases:
                raise StateError(f"unknown evaluation case: {case_id}")
        results = [self._run_case(case) for case in cases]
        return {
            "passed": sum(1 for result in results if result["passed"]),
            "failed": sum(1 for result in results if not result["passed"]),
            "results": results,
        }

    def _load_cases(self) -> list[dict[str, Any]]:
        try:
            value = json.loads(self.cases_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise StateError(f"cannot load evaluation cases: {error}") from error
        cases = value.get("cases") if isinstance(value, dict) else None
        if not isinstance(cases, list):
            raise StateError("evals/cases.json must contain a cases list")
        return cases

    def _run_case(self, case: dict[str, Any]) -> dict[str, Any]:
        checks: list[dict[str, Any]] = []
        for assertion in case.get("assertions", []):
            assertion_type = assertion.get("type")
            expected = assertion.get("expected")
            actual: Any
            if assertion_type == "path-exists":
                actual = (self.root / str(assertion["path"])).exists()
            elif assertion_type == "glob-count":
                actual = len(list(self.root.glob(str(assertion["pattern"]))))
            elif assertion_type == "json-value":
                value = json.loads((self.root / str(assertion["path"])).read_text(encoding="utf-8"))
                actual = _json_pointer(value, str(assertion["pointer"]))
            elif assertion_type == "agent-safe-defaults":
                actual = self._agent_safe_defaults()
            else:
                actual = f"unsupported assertion type: {assertion_type}"
            checks.append(
                {
                    "type": assertion_type,
                    "expected": expected,
                    "actual": actual,
                    "passed": actual == expected,
                }
            )
        return {
            "id": case.get("id"),
            "prompt": case.get("prompt"),
            "passed": bool(checks) and all(check["passed"] for check in checks),
            "checks": checks,
        }

    def _agent_safe_defaults(self) -> bool:
        mutation_tools = {"write", "shell", "@blender", "@unity"}
        for path in self.root.glob("agents/*.agent-spec.json"):
            value = json.loads(path.read_text(encoding="utf-8"))
            allowed = set(value.get("clientConfig", {}).get("kiroCli", {}).get("allowedTools", []))
            if allowed & mutation_tools:
                return False
        return True


def _json_pointer(value: Any, pointer: str) -> Any:
    current = value
    for part in pointer.strip("/").split("/") if pointer != "/" else []:
        if isinstance(current, list):
            current = current[int(part)]
        elif isinstance(current, dict):
            current = current[part]
        else:
            raise StateError(f"cannot resolve JSON pointer {pointer}")
    return current
