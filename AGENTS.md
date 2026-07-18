# AGENTS.md

## Purpose

This repository contains a dependency-free Python CLI, shared AIM-style agent specs, granular skills, and persistent Blender-to-Unity pipeline definitions for both Kiro CLI and Claude Code.

## Conventions

- Python requires 3.11 or newer and uses `src/gamedev_agent`.
- Runtime code MUST remain free of third-party Python dependencies unless a concrete adapter requires one.
- `agents/*.agent-spec.json`, `skills/`, and `agent-sops/` are shared source; client-native files MUST be generated from them rather than maintained as divergent copies.
- `state/manifest.json` is the auditable source of truth and remains versioned.
- `state/sessions/`, `state/approvals.json`, `.kiro/agents/`, `.claude/skills/gamedev-agent/`, and `logs/*.jsonl` are local runtime data and remain ignored.
- Agent names, spec filenames, skill directories, and pipeline names use lowercase kebab-case.
- Agent tool access starts restrictive. Read-only tools MAY be pre-approved; mutation remains interactive.
- Claude plugin hooks and MCP servers belong at plugin scope because plugin subagents ignore agent-level `hooks`, `mcpServers`, and `permissionMode`.
- Skills MUST keep required YAML frontmatter and Overview, Usage, and Core Concepts sections.
- SOPs MUST keep Overview, Parameters, ordered Steps, and RFC 2119 Constraints.
- Blender and Unity MCP implementation details MUST remain configurable and use server names `blender` and `unity`.
- Do not add CI/CD, authentication, broad permissions, or heavyweight operational infrastructure.

## Testing

Run these focused checks after code or capability changes:

1. Unit and mocked-MCP tests:
   `PYTHONPATH=src python -m unittest discover -s tests -v`
2. Deterministic capability evaluations:
   `PYTHONPATH=src python -m gamedev_agent.cli eval`
3. Python syntax smoke check:
   `python -m compileall -q src hooks`
4. Agent, skill, or SOP validators when those files change.
5. Generate both adapters and validate the Claude plugin:
   `gamedev agents install --client all`
   `claude plugin validate .claude/skills/gamedev-agent --strict`

For changes that affect a real Blender or Unity adapter, also run `gamedev doctor` and one small interactive scene pipeline with both applications running. This application integration check is environment-dependent and MUST NOT be simulated as a successful live check.
