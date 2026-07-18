"""Generate client-native agents/plugins and run the GameDev orchestrator."""

from __future__ import annotations

import copy
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from . import __version__
from .storage import StateError
from .telemetry import AuditLogger

Client = Literal["kiro", "claude"]

_ENV_PATTERN = re.compile(r"\{\{aim:env:([^}:]+)(?::([^}]*))?}}")
_FILE_PATTERN = re.compile(r"\{\{aim:filepath:([^}]+)}}")
_CLAUDE_PLUGIN_NAME = "gamedev-agent"
_CLAUDE_PLUGIN_RELATIVE = Path(".claude") / "skills" / _CLAUDE_PLUGIN_NAME
_CLAUDE_PLUGIN_AGENT_FIELDS = (
    "model",
    "effort",
    "maxTurns",
    "tools",
    "disallowedTools",
    "skills",
    "memory",
    "background",
    "isolation",
)


@dataclass(frozen=True)
class AgentRunResult:
    returncode: int
    stdout: str | None
    stderr: str | None
    duration_seconds: float


def install_agents(root: Path, client: Client) -> list[Path]:
    """Generate native capability files for one supported client."""
    if client == "kiro":
        return install_kiro_agents(root)
    return install_claude_plugin(root)


def install_kiro_agents(root: Path) -> list[Path]:
    """Translate repository AIM specs into workspace-local Kiro configurations."""
    root = root.resolve()
    destination = root / ".kiro" / "agents"
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".agents-", dir=destination.parent))
    try:
        for spec_path in _agent_spec_paths(root):
            spec = _load_spec(spec_path)
            config = copy.deepcopy(spec.get("clientConfig", {}).get("kiroCli", {}))
            config["name"] = spec["name"]
            config["description"] = spec["config"]["description"]
            config["prompt"] = spec["config"].get("systemPrompt", "")
            resources = list(config.get("resources", []))
            for skill_name in _dependency_names(spec, "skills", "skillNames"):
                if "*" not in skill_name:
                    resources.append(f"skill://../../skills/{skill_name}/SKILL.md")
            for sop_name in _dependency_names(spec, "agentSops", "agentSopNames"):
                if "*" not in sop_name:
                    resources.append(f"file://../../agent-sops/{sop_name}.sop.md")
            if resources:
                config["resources"] = sorted(set(resources))
            resolved = _resolve_templates(config, root)
            _drop_unavailable_default_mcp_commands(resolved)
            _write_json(temporary / f"{spec['name']}.json", resolved)

        if destination.exists():
            shutil.rmtree(destination)
        temporary.replace(destination)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return sorted(destination.glob("*.json"))


# Backward-compatible name for callers using the original Kiro-only API.
install_local_agents = install_kiro_agents


def install_claude_plugin(root: Path) -> list[Path]:
    """Generate a project-local Claude Code plugin from shared AIM-style sources."""
    root = root.resolve()
    specs = [_load_spec(path) for path in _agent_spec_paths(root)]
    destination = root / _CLAUDE_PLUGIN_RELATIVE
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{_CLAUDE_PLUGIN_NAME}-", dir=destination.parent))
    try:
        _write_json(
            temporary / ".claude-plugin" / "plugin.json",
            {
                "name": _CLAUDE_PLUGIN_NAME,
                "displayName": "GameDevAgent",
                "version": __version__,
                "description": (
                    "Persistent multi-agent Blender-to-Unity game development with "
                    "traceable assets and resumable pipelines."
                ),
                "author": {"name": "GameDevAgent contributors"},
                "license": "Apache-2.0",
                "keywords": ["blender", "unity", "game-development", "multi-agent"],
            },
        )
        for spec in specs:
            output = temporary / "agents" / f"{spec['name']}.md"
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(_render_claude_agent(spec), encoding="utf-8")

        shutil.copytree(root / "skills", temporary / "skills", dirs_exist_ok=True)
        for sop_path in sorted((root / "agent-sops").glob("*.sop.md")):
            name = sop_path.name.removesuffix(".sop.md")
            output = temporary / "skills" / name / "SKILL.md"
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(_render_claude_sop_skill(name, sop_path), encoding="utf-8")

        hook_destination = temporary / "hooks" / "pre_tool_use.py"
        hook_destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(root / "hooks" / "pre_tool_use.py", hook_destination)
        _write_json(temporary / "hooks" / "hooks.json", _claude_hooks())
        _write_json(temporary / ".mcp.json", {"mcpServers": _claude_mcp_servers(specs, root)})

        if destination.exists():
            shutil.rmtree(destination)
        temporary.replace(destination)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return sorted(path for path in destination.rglob("*") if path.is_file())


def run_agent(
    root: Path,
    *,
    prompt: str,
    agent: str = "project-manager",
    client: Client = "kiro",
    headless: bool = False,
    trusted_tools: list[str] | None = None,
) -> AgentRunResult:
    """Invoke one supported CLI without silently expanding trust."""
    executable_name = "kiro-cli" if client == "kiro" else "claude"
    executable = shutil.which(executable_name)
    if executable is None:
        raise StateError(f"{executable_name} is not installed or not on PATH")
    if client == "kiro":
        command = [executable, "chat", "--agent", agent]
        if headless:
            command.append("--no-interactive")
            if trusted_tools:
                command.append(f"--trust-tools={','.join(trusted_tools)}")
    else:
        plugin = root.resolve() / _CLAUDE_PLUGIN_RELATIVE
        if not plugin.is_dir():
            raise StateError("Claude plugin is not installed; run agents install --client claude")
        command = [
            executable,
            "--plugin-dir",
            str(plugin),
            "--agent",
            f"{_CLAUDE_PLUGIN_NAME}:{agent}",
        ]
        if headless:
            command.append("--print")
            if trusted_tools:
                command.extend(["--allowedTools", ",".join(_claude_trusted_tools(trusted_tools))])
    command.append(prompt)
    audit = AuditLogger(root)
    audit.record(
        event="agent-run-started",
        actor=agent,
        details={
            "client": client,
            "headless": headless,
            "trusted_tools": trusted_tools or [],
        },
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
        details={
            "client": client,
            "returncode": result.returncode,
            "duration_seconds": round(duration, 3),
        },
    )
    return AgentRunResult(result.returncode, result.stdout, result.stderr, duration)


def _agent_spec_paths(root: Path) -> list[Path]:
    paths = sorted((root / "agents").glob("*.agent-spec.json"))
    if not paths:
        raise StateError("no agent specs found under agents/")
    return paths


def _load_spec(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise StateError(f"agent spec must contain an object: {path}")
    return value


def _dependency_names(spec: dict[str, Any], dependency: str, field: str) -> list[str]:
    value = spec.get("dependencies", {}).get(dependency, {}).get(field, [])
    return [str(item) for item in value] if isinstance(value, list) else []


def _render_claude_agent(spec: dict[str, Any]) -> str:
    config = copy.deepcopy(spec.get("clientConfig", {}).get("claudeCli", {}))
    config.pop("hooks", None)
    config.pop("mcpServers", None)
    config.pop("permissionMode", None)
    skills = _dependency_names(spec, "skills", "skillNames")
    skills.extend(_dependency_names(spec, "agentSops", "agentSopNames"))
    if skills:
        config["skills"] = sorted(set(skills))
    if "model" not in config and spec.get("config", {}).get("model"):
        config["model"] = spec["config"]["model"]
    tools = config.get("tools")
    if isinstance(tools, list):
        config["tools"] = [_scope_claude_tool(str(tool)) for tool in tools]

    frontmatter: dict[str, Any] = {
        "name": spec["name"],
        "description": spec["config"]["description"],
    }
    for field in _CLAUDE_PLUGIN_AGENT_FIELDS:
        if field in config:
            frontmatter[field] = config[field]
    rendered = ["---"]
    rendered.extend(
        f"{key}: {json.dumps(value, ensure_ascii=False)}" for key, value in frontmatter.items()
    )
    rendered.extend(["---", "", str(spec["config"].get("systemPrompt", "")).strip(), ""])
    return "\n".join(rendered)


def _scope_claude_tool(tool: str) -> str:
    prefix = "mcp__"
    suffix = "__*"
    if tool.startswith(prefix) and tool.endswith(suffix):
        server = tool[len(prefix) : -len(suffix)]
        return f"mcp__plugin_{_CLAUDE_PLUGIN_NAME}_{server}__*"
    return tool


def _render_claude_sop_skill(name: str, path: Path) -> str:
    body = path.read_text(encoding="utf-8").strip()
    description = {
        "pipeline-scene-to-unity": (
            "Create and validate one traceable Blender scene through Unity QA and release handoff."
        ),
        "pipeline-prop-kit": (
            "Produce a traceable, consistent Blender prop kit and reusable Unity prefabs."
        ),
        "pipeline-vertical-slice": (
            "Build a bounded playable Unity vertical slice from Blender content through QA."
        ),
    }.get(name, f"Execute the {name} GameDevAgent pipeline.")
    return f"---\nname: {json.dumps(name)}\ndescription: {json.dumps(description)}\n---\n\n{body}\n"


def _claude_hooks() -> dict[str, Any]:
    return {
        "hooks": {
            "PreToolUse": [
                {
                    "matcher": ("Bash|mcp__plugin_gamedev-agent_(blender|unity)__.*"),
                    "hooks": [
                        {
                            "type": "command",
                            "command": ('python3 "${CLAUDE_PLUGIN_ROOT}/hooks/pre_tool_use.py"'),
                            "timeout": 10,
                        }
                    ],
                }
            ]
        }
    }


def _claude_mcp_servers(specs: list[dict[str, Any]], root: Path) -> dict[str, Any]:
    servers: dict[str, Any] = {}
    for spec in specs:
        configured = spec.get("clientConfig", {}).get("claudeCli", {}).get("mcpServers", {})
        if not isinstance(configured, dict):
            continue
        for name, server in configured.items():
            resolved = _resolve_templates(copy.deepcopy(server), root)
            existing = servers.get(name)
            if existing is not None and existing != resolved:
                raise StateError(f"conflicting Claude MCP configuration for {name}")
            servers[str(name)] = resolved
    wrapper = {"mcpServers": servers}
    _drop_unavailable_default_mcp_commands(wrapper)
    return wrapper.get("mcpServers", {})


def _claude_trusted_tools(tools: list[str]) -> list[str]:
    mapping = {
        "read": "Read",
        "write": "Write,Edit",
        "shell": "Bash",
        "subagent": "Agent",
        "web_search": "WebSearch",
        "web_fetch": "WebFetch",
    }
    resolved: list[str] = []
    for tool in tools:
        mapped = mapping.get(tool, tool)
        resolved.extend(item for item in mapped.split(",") if item)
    return list(dict.fromkeys(resolved))


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


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
    """Use ambient configuration when optional default MCP commands are unavailable."""
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
