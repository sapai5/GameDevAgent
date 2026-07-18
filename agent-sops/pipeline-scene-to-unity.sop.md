# Pipeline Scene to Unity

## Overview
Create one traceable Blender scene, export it under license and overwrite gates, assemble it in Unity, run play-mode QA, and prepare an approved release unit.

## Parameters

- **project_root** (required): Absolute path to the initialized GameDevAgent project.
- **scene_brief** (required): Bounded scene goal and acceptance criteria.
- **actor** (required): Human or service identity recorded in state changes.
- **session_id** (optional): Existing session to resume instead of starting another.

**Constraints for parameter acquisition:**
- If all required parameters are already provided, You MUST proceed to the Steps
- If any required parameters are missing, You MUST ask for them before proceeding
- When asking for parameters, You MUST request all parameters in a single prompt
- When asking for parameters, You MUST use the exact parameter names as defined

## Steps
### 1. Initialize or resume state
Use `gamedev status` and `gamedev resume` before creating a new session.

**Constraints:**
- You MUST validate `state/manifest.json` and run `gamedev doctor`.
- If `session_id` is present, You MUST resume that session.
- You MUST NOT start a duplicate session because parallel ownership would corrupt pipeline intent.
- If no session exists, You MUST run `gamedev pipeline start pipeline-scene-to-unity --actor <actor>`.

### 2. Plan and research
Dispatch planning to `project-manager` and external dependency research to `asset-researcher`.

**Constraints:**
- You MUST freeze asset ids, budgets, paths, and acceptance criteria from `scene_brief`.
- You MUST require `license-compliance` evidence for every external asset.
- You MUST write structured results to the manifest or session files rather than relying on conversation context.
- If a required license is unresolved, You MUST block the session.

### 3. Create the Blender scene
Dispatch geometry, materials, and composition to their narrow Blender agents in dependency order.

**Constraints:**
- You MUST use `blender-modeler`, then `blender-materials`, then `blender-scene-composer`.
- Each agent MUST return changed asset ids and paths.
- You MUST update manifest provenance after each handoff.
- You MUST NOT let an agent export outside `blender-exporter` because export policy must be consistent.

### 4. Validate and export
Dispatch the approved collection to `blender-exporter`.

**Constraints:**
- You MUST require verified licenses, correct scale, origins, names, and budgets before export.
- You MUST request one-time approval before an overwrite because the prior artifact is audit evidence.
- You MUST record export path and checksum.
- If export outcome is uncertain, You MUST inspect the destination before retrying.

### 5. Assemble in Unity
Dispatch import and scene assembly to `unity-scene-builder`.

**Constraints:**
- You MUST import from the manifest export path and verify its checksum.
- You MUST create stable prefab and scene paths.
- You MUST record the Unity import path for each asset.
- If Unity MCP is unavailable, You MUST block and preserve the current stage.

### 6. Run QA
Dispatch the frozen acceptance criteria to `unity-qa-tester`.

**Constraints:**
- You MUST require a `PASS`, `FAIL`, or `BLOCKED` result with console evidence.
- If QA fails, You MUST route each defect to its owning specialist and rerun the affected checks.
- You MUST NOT mark the stage complete because unresolved failures would invalidate release evidence.

### 7. Prepare release
Dispatch the completed unit to `release-engineer` and request the pipeline-stage approval.

**Constraints:**
- You MUST verify Git hygiene, metadata, LFS, tests, QA, manifest checksums, and staged scope.
- You MUST show the proposed commit and request human approval before Git mutation.
- You MUST run `gamedev pipeline advance` only after the `pipeline.stage` approval is consumed.

## Examples

### Create a small environment
**Input:**
- project_root: `/projects/forest-game`
- scene_brief: `A moonlit clearing with five traceable props and one fixed camera`
- actor: `developer`

**Expected behavior:** The orchestrator creates or resumes one session, routes each stage to its named agent, and blocks at unresolved license, QA, overwrite, or release gates.

## Troubleshooting

### MCP unavailable
Run `gamedev doctor`, restart only the unavailable application or MCP server, and run `gamedev resume`.

### Export result uncertain
Inspect the destination path and checksum before issuing another export request.
