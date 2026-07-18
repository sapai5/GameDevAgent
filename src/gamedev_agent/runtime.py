"""Install AIM-style specs as local Kiro agents and run the orchestrator."""

from __future__ import annotations

import copy
import json
import os
import re
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .storage import StateError
from .telemetry import AuditLogger

_ENV_PATTERN = re.compile(r"\{\{aim:env:([^}:]+)(?::([^}]*))?}}")
_FILE_PATTERN = re.compile(r"\{\{aim:filepath:([^}]+)}}")


@dataclass(frozen=True)
class AgentRunResult:
    returncode: int
    stdout: str | None
    stderr: str | None
    duration_seconds: float


def install_local_agents(root: Path) -> list[Path]:
    """Translate repository AIM specs into workspace-local Kiro configurations."""
    root = root.resolve()
    destination = root / ".kiro" / "agents"
    destination.mkdir(parents=True, exist_ok=True)
    installed: list[Path] = []
    for spec_path in sorted((root / "agents").glob("*.agent-spec.json")):
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
        config = copy.deepcopy(spec.get("clientConfig", {}).get("kiroCli", {}))
        config["name"] = spec["name"]
        config["description"] = spec["config"]["description"]
        config["prompt"] = spec["config"].get("systemPrompt", "")
        resources = list(config.get("resources", []))
        for skill_name in spec.get("dependencies", {}).get("skills", {}).get("skillNames", []):
            if "*" not in skill_name:
                resources.append(f"skill://../../skills/{skill_name}/SKILL.md")
        for sop_name in spec.get("dependencies", {}).get("agentSops", {}).get("agentSopNames", []):
            if "*" not in sop_name:
                resources.append(f"file://../../agent-sops/{sop_name}.sop.md")
        if resources:
            config["resources"] = sorted(set(resources))
        resolved = _resolve_templates(config, root)
        _drop_unavailable_default_mcp_commands(resolved)
        output = destination / f"{spec['name']}.json"
        output.write_text(json.dumps(resolved, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        installed.append(output)
    if not installed:
        raise StateError("no agent specs found under agents/")
    return installed


def run_agent(
    root: Path,
    *,
    prompt: str,
    agent: str = "project-manager",
    headless: bool = False,
    trusted_tools: list[str] | None = None,
) -> AgentRunResult:
    """Invoke Kiro CLI without silently expanding trust."""
    executable = shutil.which("kiro-cli")
    if executable is None:
        raise StateError("kiro-cli is not installed or not on PATH")
    command = [executable, "chat", "--agent", agent]
    if headless:
        command.append("--no-interactive")
        if trusted_tools:
            command.append(f"--trust-tools={','.join(trusted_tools)}")
    command.append(prompt)
    audit = AuditLogger(root)
    audit.record(
        event="agent-run-started",
        actor=agent,
        details={"headless": headless, "trusted_tools": trusted_tools or []},
    )
    started = time.monotonic()
    result = subprocess.run(
        command,
        cwd=root,
        text=True,
        capture_output=headless,
        check=False,
    )
    duration = time.monotonic() - started
    audit.record(
        event="agent-run-finished",
        actor=agent,
        outcome="success" if result.returncode == 0 else "failure",
        details={"returncode": result.returncode, "duration_seconds": round(duration, 3)},
    )
    return AgentRunResult(result.returncode, result.stdout, result.stderr, duration)


def _resolve_templates(value: Any, root: Path) -> Any:
    if isinstance(value, dict):
        return {key: _resolve_templates(item, root) for key, item in value.items()}
    if isinstance(value, list):
        return [_resolve_templates(item, root) for item in value]
    if not isinstance(value, str):
        return value

    def replace_environment(match: re.Match[str]) -> str:
        name, default = match.groups()
        environment = os.environ.get(name)
        if environment is not None:
            return environment
        if default is None:
            raise StateError(f"required environment variable is unset: {name}")
        return default

    value = _ENV_PATTERN.sub(replace_environment, value)
    return _FILE_PATTERN.sub(lambda match: str((root / match.group(1)).resolve()), value)


def _drop_unavailable_default_mcp_commands(config: dict[str, Any]) -> None:
    """Use ambient mcp.json when optional default command names are unavailable."""
    servers = config.get("mcpServers")
    if not isinstance(servers, dict):
        return
    for name, server in list(servers.items()):
        if not isinstance(server, dict):
            continue
        command = server.get("command")
        unavailable_command = (
            isinstance(command, str)
            and os.path.sep not in command
            and shutil.which(command) is None
        )
        if unavailable_command:
            del servers[name]
    if not servers:
        config.pop("mcpServers", None)
