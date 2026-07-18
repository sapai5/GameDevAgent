# Pipeline Vertical Slice

## Overview
Build one MVP-sized level with a core mechanic, minimum art and audio, basic UI, a target-platform build, regression evidence, and an approved release unit.

## Parameters

- **project_root** (required): Absolute path to the initialized GameDevAgent project.
- **slice_brief** (required): Player loop, one core mechanic, level goal, target platform, budgets, and acceptance criteria.
- **actor** (required): Human or service identity recorded in state changes.
- **session_id** (optional): Existing vertical-slice session to resume.

**Constraints for parameter acquisition:**
- If all required parameters are already provided, You MUST proceed to the Steps
- If any required parameters are missing, You MUST ask for them before proceeding
- When asking for parameters, You MUST request all parameters in a single prompt
- When asking for parameters, You MUST use the exact parameter names as defined

## Steps
### 1. Freeze slice scope
Initialize or resume `pipeline-vertical-slice` and persist the brief.

**Constraints:**
- You MUST run `gamedev status`, `gamedev doctor`, and `gamedev resume` before starting work.
- You MUST define one player loop, one core mechanic, one level, target platform, and out-of-scope list.
- You MUST NOT add unplanned features because scope growth prevents an MVP-sized completion signal.

### 2. Resolve external dependencies
Dispatch required asset and library research to `asset-researcher`.

**Constraints:**
- You MUST research only dependencies required by the frozen slice.
- You MUST pass every external item through `license-compliance`.
- You MUST block unresolved dependencies instead of substituting untracked content.

### 3. Create and export minimum art
Dispatch environment geometry, look development, composition, and export to the four Blender agents in order.

**Constraints:**
- You MUST minimize assets to those required by the player loop.
- You MUST enforce shared ids, dimensions, budgets, and target render-pipeline material rules.
- You MUST record Blender source, export path, checksum, provenance, and verified license per asset.
- You MUST request approval before deleting source data or overwriting exports.

### 4. Assemble the Unity level
Dispatch import, prefabs, scene composition, and camera setup to `unity-scene-builder`.

**Constraints:**
- You MUST import only verified manifest artifacts.
- You MUST create stable paths and resolve all missing references before gameplay work.
- You MUST preserve a deterministic validation entry scene.

### 5. Implement the core mechanic
Dispatch gameplay and input to `unity-gameplay-programmer`, then physical behavior to `unity-physics-engineer`.

**Constraints:**
- You MUST implement only behavior required by the frozen mechanic.
- You MUST require targeted automated tests and explicit scene bindings.
- You MUST validate missing dependencies, input transitions, collision, and reset behavior.

### 6. Add minimum UI and audio
Dispatch HUD and menus to `unity-ui-programmer` using licensed audio assets when required.

**Constraints:**
- You MUST implement only feedback necessary to understand and complete the loop.
- You MUST support required resolutions and control-scheme navigation.
- You MUST preserve audio provenance and mixer routing.

### 7. Create a target build
Dispatch target configuration and build output to `unity-build-engineer`.

**Constraints:**
- You MUST record scene list, player settings, target, output path, warnings, and build result.
- You MUST request approval before overwriting a build directory.
- You MUST launch the built player and capture a smoke result.

### 8. Run regression and budget checks
Dispatch the built slice and acceptance criteria to `unity-qa-tester`.

**Constraints:**
- You MUST execute the complete player loop and inspect console or player logs.
- You MUST compare performance evidence with the frozen budgets.
- If QA fails, You MUST route defects to owners and rerun the affected checks and final smoke path.
- You MUST NOT release with unresolved failures because the slice would not demonstrate the promised loop.

### 9. Prepare release
Dispatch the validated slice to `release-engineer` and request final approval.

**Constraints:**
- You MUST verify tests, QA, build evidence, manifest checksums, metadata, LFS, ignores, and staged scope.
- You MUST present the exact proposed commit before requesting Git approval.
- You MUST consume `pipeline.stage` approval before completing the session.

## Examples

### Interaction slice
**Input:**
- project_root: `/projects/ruins-game`
- slice_brief: `Explore one room, pick up one key, open one door, and show completion on macOS`
- actor: `developer`

**Expected behavior:** The pipeline rejects unrelated combat or inventory expansion and produces a tested build of the single promised loop.

## Troubleshooting

### Scope expands during implementation
Record the request as future scope and continue against the frozen acceptance criteria unless the human explicitly restarts planning.

### Build passes but player loop fails
Treat the pipeline as failed, route the defect to its owner, and rerun build smoke plus full QA.
