# GameDevAgent

GameDevAgent is a local CLI plus a package of narrow Kiro agents and skills for creating Blender assets, moving validated exports into Unity, and building game-development slices over multiple sessions. It keeps asset provenance and pipeline progress on disk instead of treating each prompt as an isolated run.

## What works

- `gamedev run` installs the 13 repository agents as workspace-local Kiro agents and invokes `project-manager` interactively.
- Three resumable pipelines cover a scene handoff, a consistent prop kit, and an MVP vertical slice.
- Blender and Unity remain external MCP building blocks; their exact implementations are configurable rather than coupled to this package.
- Every manifest asset records source type and agent, license evidence, Blender source, export path, Unity path, checksum, history, and last modifier.
- Pipeline sessions survive process restarts under `state/sessions/`.
- Tool and agent-run audit records use JSON Lines under `logs/`.
- Open-source research uses Kiro's `web_search` and `web_fetch` tools and an independent license gate.

## Install

Python 3.11 or newer and Kiro CLI are required. The package has no runtime Python dependencies.

```bash
uv venv --python 3.11
. .venv/bin/activate
uv pip install -e .
gamedev init --name my-game --actor "$USER"
gamedev agents install
```

`gamedev agents install` translates `agents/*.agent-spec.json` into ignored workspace-local `.kiro/agents/*.json` files. The AIM-style source specs remain the versioned source of truth.

## Configure Blender and Unity MCP

Agent specs use configurable stdio commands:

```bash
export GAMEDEV_BLENDER_MCP_COMMAND=/absolute/path/to/blender-mcp
export GAMEDEV_UNITY_MCP_COMMAND=/absolute/path/to/unity-mcp

gamedev agents install
```

If those variables are unset and the default `blender-mcp` or `unity-mcp` command is unavailable, the local installer omits that server declaration and Kiro may use servers from workspace or user `mcp.json` instead. Keep their server names `blender` and `unity`, because agent tool scopes use `@blender` and `@unity`.

`gamedev doctor` checks HTTP JSON-RPC endpoints used by the CLI adapter. Set them independently when your MCP servers expose HTTP:

```bash
export GAMEDEV_BLENDER_MCP_URL=http://127.0.0.1:<port>/mcp
export GAMEDEV_UNITY_MCP_URL=http://127.0.0.1:<port>/mcp
gamedev doctor
```

You can place the same URLs in `gamedev.json`. No port is assumed.

## Run game-development work

Interactive mode is the default and recommended mode because Kiro can request approval for mutations:

```bash
gamedev run \
  --pipeline pipeline-scene-to-unity \
  "Create a moonlit forest clearing with five reusable props, import it into Unity, and validate it in play mode"
```

Available pipelines:

- `pipeline-scene-to-unity` — one Blender scene through Unity QA
- `pipeline-prop-kit` — a themed batch of consistent reusable props
- `pipeline-vertical-slice` — level, one core mechanic, minimum UI/audio, target build, and QA

Headless mode is explicit and adds no trust by default:

```bash
gamedev run --headless --trust-tools read,subagent \
  "Research compatible open-source foliage libraries and record candidates"
```

A headless run fails fast if an untrusted tool needs approval. Do not use broad trust merely to make automation continue.

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

Later stages update the same asset instead of editing JSON directly:

```bash
gamedev asset update \
  --id forest-crate-a \
  --actor unity-scene-builder \
  --unity-path Unity/Assets/Game/Art/Imported/SM_ForestCrate_A.glb
```

Use `--export-file` after export, or `--license`, `--license-url`, and
`--license-verified` after compliance review. Use `--no-license-verified` to revoke a
previous verification. Every update refreshes `last_modified_by` and appends history;
source/export changes also recalculate the checksum when the file exists.

After file contents change without a path change, run `gamedev asset checksum --id forest-crate-a --actor blender-exporter`.

## Approval gate

The shared Kiro `preToolUse` hook blocks classified deletion, export overwrite, and destructive Git commands unless a matching one-time approval exists. The block message prints the exact command. Example:

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
5. Leave blocked/failed session evidence in place for diagnosis.

## Usage records

Kiro CLI's documented headless interface does not expose a machine-readable cost result. When a caller has ResultMessage usage values, record them explicitly:

```bash
gamedev usage record --agent blender-modeler --turns 3 --cost-usd 0.42 --session <id>
gamedev usage summary
```

The runner always records start, finish, return code, and duration in `logs/audit.jsonl`.

## Layout

```text
agents/          13 AIM-style narrow agent specs
agent-sops/      3 executable pipeline SOPs
skills/          29 granular domain skills
pipelines/       persistent JSON stage definitions
src/             dependency-free Python CLI and orchestration
state/           versioned manifest plus ignored runtime sessions/approvals
logs/            ignored JSONL audit and usage logs
evals/           deterministic prompt/outcome checks
hooks/           shared Kiro preToolUse safety hook
tests/           focused state, MCP, gate, and CLI checks
```

## Local validation

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
PYTHONPATH=src python -m gamedev_agent.cli eval
python -m compileall -q src hooks
```

The external Blender/Unity smoke check is `gamedev doctor` followed by one small interactive scene pipeline while both applications are running.
