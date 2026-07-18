# GameDevAgent

GameDevAgent is a dependency-free Python CLI and shared capability package for Kiro CLI and Claude Code. It coordinates narrow Blender and Unity specialists across resumable pipelines while keeping asset provenance and pipeline state on disk.

## What works

- `gamedev run --client kiro` installs 13 workspace-local Kiro agents and runs `project-manager`.
- `gamedev run --client claude` generates and loads a native Claude Code plugin with the same 13 agents, 29 skills, three pipeline skills, safety hook, and Blender/Unity MCP configuration.
- Three resumable pipelines cover a scene handoff, a consistent prop kit, and an MVP vertical slice.
- Blender and Unity remain configurable external MCP building blocks rather than package-specific implementations.
- Every manifest asset records source type and agent, license evidence, Blender source, export path, Unity path, checksum, history, and last modifier.
- Pipeline sessions survive process restarts under `state/sessions/`; audit and usage records use JSON Lines under `logs/`.
- Open-source research uses each client's native web search and fetch tools and an independent license gate.

The versioned AIM-style specs in `agents/`, shared `skills/`, and SOPs in `agent-sops/` are the source of truth. Client-native files are generated locally and ignored by Git.

## Install

Python 3.11 or newer and at least one supported client are required. No runtime Python dependencies or authentication framework are added by this package.

```bash
uv venv --python 3.11
. .venv/bin/activate
uv pip install -e .
gamedev init --name my-game --actor "$USER"
```

Install one or both client adapters:

```bash
gamedev agents install --client kiro
gamedev agents install --client claude
gamedev agents install --client all
```

The default remains Kiro for backward compatibility. Generated outputs are:

- Kiro: `.kiro/agents/*.json`
- Claude Code: `.claude/skills/gamedev-agent/`

The Claude output is a native project-scoped skills-directory plugin. Claude Code discovers it when launched from the repository root after workspace trust is accepted; `gamedev run --client claude` also loads it explicitly with `--plugin-dir`.

## Configure Blender and Unity MCP

The shared specs use configurable stdio commands:

```bash
export GAMEDEV_BLENDER_MCP_COMMAND=/absolute/path/to/blender-mcp
export GAMEDEV_UNITY_MCP_COMMAND=/absolute/path/to/unity-mcp
gamedev agents install --client all
```

Configuration is resolved at install time, so reinstall the client adapters after changing either variable. If a variable is unset and the default `blender-mcp` or `unity-mcp` executable is unavailable, that generated server declaration is omitted instead of creating a broken process. Keep the server names `blender` and `unity`; both adapters derive tool scopes from those names.

`gamedev doctor` independently checks HTTP JSON-RPC endpoints used by the CLI adapter:

```bash
export GAMEDEV_BLENDER_MCP_URL=http://127.0.0.1:<port>/mcp
export GAMEDEV_UNITY_MCP_URL=http://127.0.0.1:<port>/mcp
gamedev doctor
```

The same URLs can be placed in `gamedev.json`. No port is assumed.

## Run game-development work

Interactive mode is the default and recommended mode because either client can request approval for mutations:

```bash
gamedev run --client kiro \
  --pipeline pipeline-scene-to-unity \
  "Create a moonlit forest clearing, import it into Unity, and validate play mode"

gamedev run --client claude \
  --pipeline pipeline-vertical-slice \
  "Build one level with one movement mechanic, minimum HUD, a target build, and QA"
```

Available pipelines:

- `pipeline-scene-to-unity` — one Blender scene through Unity QA
- `pipeline-prop-kit` — a themed batch of consistent reusable props
- `pipeline-vertical-slice` — level, one core mechanic, minimum UI/audio, target build, and QA

In Claude Code, the pipeline SOPs are also namespaced skills:

```text
/gamedev-agent:pipeline-scene-to-unity
/gamedev-agent:pipeline-prop-kit
/gamedev-agent:pipeline-vertical-slice
```

Headless mode is explicit and adds no trust by default:

```bash
gamedev run --client kiro --headless --trust-tools read,subagent \
  "Research compatible foliage libraries and record candidates"

gamedev run --client claude --headless --trust-tools read,subagent \
  "Research compatible foliage libraries and record candidates"
```

For Claude, the explicit trust names are mapped to native names such as `Read` and `Agent` and passed through `--allowedTools`. The runner never enables `bypassPermissions` or broad trust.

## Persistent commands

```bash
gamedev status
gamedev resume
gamedev manifest
gamedev manifest --output reports/manifest.json
gamedev pipeline list
gamedev pipeline start pipeline-prop-kit --actor project-manager
gamedev pipeline advance --session <id> --actor blender-modeler
gamedev eval
```

Register a traceable asset:

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

Later stages update that asset instead of editing JSON directly:

```bash
gamedev asset update \
  --id forest-crate-a \
  --actor unity-scene-builder \
  --unity-path Unity/Assets/Game/Art/Imported/SM_ForestCrate_A.glb
```

Use `--export-file` after export, or `--license`, `--license-url`, and `--license-verified` after compliance review. Use `--no-license-verified` to revoke verification. Every update refreshes `last_modified_by` and appends history; source/export changes recalculate the checksum when the file exists. After contents change without a path change, run `gamedev asset checksum --id forest-crate-a --actor blender-exporter`.

## Approval gate

The shared classifier blocks Blender/Unity deletion, export overwrite, and destructive Git commands unless a matching one-time approval exists. Kiro invokes it through `preToolUse`; the Claude plugin invokes it through plugin-level `PreToolUse` because Claude plugin subagents do not honor agent-level hooks.

```bash
gamedev approve \
  --operation blender.delete \
  --resource Cube \
  --actor "$USER"
```

Approvals expire in 15 minutes by default and are consumed once. Pipeline release stages use operation `pipeline.stage` and resource `<session-id>:<stage-id>`.

## Recovery

1. Run `gamedev status` and `gamedev resume`; do not start a duplicate pipeline.
2. Run `gamedev doctor` when Blender or Unity is unavailable.
3. Retry idempotent reads within the bounded MCP retry policy.
4. Inspect scene or output state before repeating a timed-out mutation.
5. Leave blocked or failed session evidence in place for diagnosis.

## Usage records

When a caller has usage values, record them explicitly:

```bash
gamedev usage record --agent blender-modeler --turns 3 --cost-usd 0.42 --session <id>
gamedev usage summary
```

The runner records client, start, finish, return code, and duration in `logs/audit.jsonl`.

## Layout

```text
agents/          13 shared AIM-style narrow agent specs
agent-sops/      3 executable pipeline SOPs
skills/          29 granular domain skills
pipelines/       persistent JSON stage definitions
src/             dependency-free Python CLI and client adapters
state/           versioned manifest plus ignored sessions/approvals
logs/            ignored JSONL audit and usage logs
hooks/           shared destructive-operation classifier entrypoint
evals/           deterministic prompt/outcome checks
tests/           focused state, MCP, gate, CLI, and adapter checks
```

## Local validation

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
PYTHONPATH=src python -m gamedev_agent.cli eval
python -m compileall -q src hooks
gamedev agents install --client claude
claude plugin validate .claude/skills/gamedev-agent --strict
```

The external application smoke check is `gamedev doctor` followed by one small interactive pipeline while Blender and Unity are running. Do not report a simulated or unconfigured application check as a successful live run.
