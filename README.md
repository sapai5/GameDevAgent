# GameDevAgent for Claude Code

GameDevAgent is a native Claude Code plugin and local CLI for building Blender assets, importing validated exports into Unity, and developing playable game slices across multiple sessions. A project-manager agent coordinates 12 narrow specialists while the CLI persists asset provenance, pipeline progress, approvals, and audit records on disk.

## Capabilities

- Creates Blender geometry, materials, UVs, lighting, cameras, and composed scenes through Blender MCP.
- Exports validated glTF or FBX assets and imports them into Unity through Unity MCP.
- Builds Unity scenes, prefabs, gameplay, physics, UI, audio, platform settings, and testable builds.
- Uses Claude Code `WebSearch` and `WebFetch` to research open-source assets and libraries.
- Tracks each asset's source, license, Blender file, export path, Unity path, SHA-256 checksum, history, and last modifying agent.
- Resumes interrupted work from persistent pipeline sessions instead of relying on conversation history.
- Blocks destructive Git commands, Blender or Unity deletion, and export overwrites without a matching one-time approval.

## Claude Code plugin

The generated plugin contains:

- 13 focused agents in `agents/`
- 29 shared game-development skills
- 3 executable pipeline skills generated from the repository SOPs
- Plugin-level `PreToolUse` safety hooks
- Optional `blender` and `unity` MCP server declarations

The versioned files under `agents/`, `skills/`, and `agent-sops/` are the source of truth. Installation generates the native plugin at `.claude/skills/gamedev-agent/`. Git ignores this directory, and each install replaces it atomically. Edit the versioned source files. Do not edit generated output.

## Prerequisites

- Python 3.11 or newer
- [Claude Code](https://docs.anthropic.com/en/docs/claude-code/overview) installed and authenticated
- Blender and Unity MCP servers for application control
- `uv` for the commands below, or another Python package installer

The Python runtime has no third-party dependencies.

## Quick start

From the repository root:

```bash
uv venv --python 3.11
. .venv/bin/activate
uv pip install -e .

gamedev init --name my-game --actor "$USER"
gamedev agents install --client claude
claude plugin validate .claude/skills/gamedev-agent --strict
```

Start an interactive vertical-slice pipeline:

```bash
gamedev run --client claude \
  --pipeline pipeline-vertical-slice \
  "Build one level with one movement mechanic, a minimal HUD, a target build, and a QA pass"
```

`gamedev run` regenerates the plugin and launches Claude Code with:

```text
claude --plugin-dir .claude/skills/gamedev-agent \
  --agent gamedev-agent:project-manager
```

After you accept workspace trust, Claude Code discovers the project plugin when started from the repository root. To run it directly:

```bash
claude --plugin-dir .claude/skills/gamedev-agent \
  --agent gamedev-agent:project-manager
```

## Configure Blender and Unity MCP

Set the stdio commands before generating the plugin:

```bash
export GAMEDEV_BLENDER_MCP_COMMAND=/absolute/path/to/blender-mcp
export GAMEDEV_UNITY_MCP_COMMAND=/absolute/path/to/unity-mcp

gamedev agents install --client claude
```

The installer resolves MCP commands at install time. Reinstall the plugin after changing either variable. If a variable is unset and the default `blender-mcp` or `unity-mcp` executable is not on `PATH`, the installer omits that server instead of generating a broken declaration.

Keep the MCP server names `blender` and `unity`. Agent tool scopes and the safety hook derive their names from those identifiers.

### Check MCP connectivity

`gamedev doctor` checks HTTP JSON-RPC endpoints independently of the plugin's stdio configuration. Use it when your MCP servers expose HTTP endpoints:

```bash
export GAMEDEV_BLENDER_MCP_URL=http://127.0.0.1:<port>/mcp
export GAMEDEV_UNITY_MCP_URL=http://127.0.0.1:<port>/mcp

gamedev doctor
```

Alternatively, set the URLs under `mcp.blender.url` and `mcp.unity.url` in `gamedev.json`. Each URL must include its explicit port.

## Agents

The project-manager delegates work to these plugin subagents:

| Area | Agents |
|---|---|
| Blender | `blender-modeler`, `blender-materials`, `blender-scene-composer`, `blender-exporter` |
| Unity | `unity-scene-builder`, `unity-gameplay-programmer`, `unity-physics-engineer`, `unity-ui-programmer`, `unity-build-engineer`, `unity-qa-tester` |
| Cross-cutting | `asset-researcher`, `release-engineer` |

Each subagent has focused tools and preloaded skills. Blender and Unity tools are scoped through the plugin MCP servers. Claude Code plugin subagents do not support agent-level hooks or MCP declarations, so GameDevAgent promotes both to plugin scope during generation.

## Pipelines

Use `--pipeline` to start or resume one of three workflows:

| Pipeline | Outcome |
|---|---|
| `pipeline-scene-to-unity` | Create one Blender scene, export it, assemble it in Unity, and complete play-mode QA. |
| `pipeline-prop-kit` | Produce a consistent set of reusable Blender props and Unity prefabs. |
| `pipeline-vertical-slice` | Build one level, one core mechanic, minimum UI and audio, a target build, and QA evidence. |

The same workflows are available as namespaced Claude Code skills:

```text
/gamedev-agent:pipeline-scene-to-unity
/gamedev-agent:pipeline-prop-kit
/gamedev-agent:pipeline-vertical-slice
```

Before starting work, the project manager checks for an active session. It resumes existing work instead of creating a duplicate pipeline.

## Headless execution

Headless mode uses Claude Code `--print` and grants no trust unless you request it:

```bash
gamedev run --client claude --headless \
  "Inspect the current manifest and report the next incomplete stage"
```

Grant only the tools required for a bounded task:

```bash
gamedev run --client claude --headless \
  --trust-tools read,subagent \
  "Research compatible open-source foliage libraries and record candidates"
```

The CLI maps aliases such as `read`, `write`, `shell`, `subagent`, `web_search`, and `web_fetch` to Claude Code tool names and passes them through `--allowedTools`. It never enables `bypassPermissions` or broad trust.

## Persistent state

GameDevAgent stores durable project state outside the Claude conversation:

```text
state/manifest.json       versioned asset provenance and file records
state/sessions/*.json     ignored resumable pipeline sessions
state/approvals.json      ignored one-time approvals
logs/audit.jsonl          ignored agent-run and action audit records
logs/usage.jsonl          ignored optional usage records
```

Inspect state with:

```bash
gamedev status
gamedev resume
gamedev manifest
gamedev manifest --output reports/manifest.json
gamedev pipeline list
```

### Register an asset

```bash
gamedev asset add \
  --id forest-crate-a \
  --name "Forest Crate A" \
  --kind prop \
  --source-type hand-modeled \
  --license LicenseRef-Proprietary \
  --license-verified \
  --actor blender-modeler \
  --blender-file Blender/Props/ForestCrateA.blend \
  --export-file Exports/Props/SM_ForestCrate_A.glb \
  --unity-path Unity/Assets/Game/Art/Imported/SM_ForestCrate_A.glb
```

Later agents update the same record instead of editing JSON directly:

```bash
gamedev asset update \
  --id forest-crate-a \
  --actor unity-scene-builder \
  --unity-path Unity/Assets/Game/Art/Imported/SM_ForestCrate_A.glb
```

Use `--export-file` after export. Use `--license`, `--license-url`, and `--license-verified` after compliance review. Use `--no-license-verified` to revoke verification. Every update refreshes `last_modified_by` and appends history. Source or export path changes recalculate the checksum when the file exists.

If file contents change without a path change, refresh the checksum explicitly:

```bash
gamedev asset checksum --id forest-crate-a --actor blender-exporter
```

## Safety approvals

The plugin-level `PreToolUse` hook classifies destructive operations before Claude Code executes them. A blocked operation returns the exact approval command. For example:

```bash
gamedev approve \
  --operation blender.delete \
  --resource Cube \
  --actor "$USER"
```

Approvals expire after 15 minutes by default and are consumed once. Pipeline release gates use operation `pipeline.stage` and resource `<session-id>:<stage-id>`.

## Recovery

1. Run `gamedev status` and `gamedev resume` to find the current stage.
2. Run `gamedev doctor` when Blender or Unity is unavailable.
3. Inspect application and output state before repeating a timed-out mutation.
4. Retry only idempotent reads automatically.
5. Preserve blocked or failed session evidence for diagnosis.

## Usage records

When a caller has usage values, record them explicitly:

```bash
gamedev usage record \
  --agent blender-modeler \
  --turns 3 \
  --cost-usd 0.42 \
  --session <id>

gamedev usage summary
```

The runner always records the client, start and finish events, return code, and duration in `logs/audit.jsonl`.

## Repository layout

```text
agents/          13 shared agent specifications with Claude Code configuration
agent-sops/      3 pipeline SOPs converted to plugin skills
skills/          29 granular Blender, Unity, and cross-cutting skills
pipelines/       persistent JSON stage definitions
src/             dependency-free Python CLI and Claude plugin generator
state/           versioned manifest plus ignored sessions and approvals
hooks/           shared destructive-operation classifier
logs/            ignored JSONL audit and usage logs
evals/           deterministic capability checks
tests/           state, MCP, safety, CLI, and plugin-generator tests
```

## Validate changes

```bash
uv run --python 3.11 --no-project --with ruff==0.12.5 ruff format --check src tests hooks
uv run --python 3.11 --no-project --with ruff==0.12.5 ruff check src tests hooks
uv run --python 3.11 --no-project --with mypy==1.17.0 mypy src/gamedev_agent
uv run --python 3.11 --no-project --with-editable . python -m unittest discover -s tests -v
uv run --python 3.11 --no-project --with-editable . python -m gamedev_agent.cli eval

gamedev agents install --client claude
claude plugin validate .claude/skills/gamedev-agent --strict
```

For an application smoke test, start Blender and Unity with their MCP servers, run `gamedev doctor`, and execute one small interactive pipeline. Do not treat mocked or unconfigured MCP checks as a successful live application test.
