# Pipeline Prop Kit

## Overview
Batch-produce a themed set of consistent, traceable Blender props, convert them to Unity prefabs, validate the complete kit, and prepare one release unit.

## Parameters

- **project_root** (required): Absolute path to the initialized GameDevAgent project.
- **kit_brief** (required): Theme, exact prop list, shared dimensions, budgets, and acceptance criteria.
- **actor** (required): Human or service identity recorded in state changes.
- **session_id** (optional): Existing prop-kit session to resume.

**Constraints for parameter acquisition:**
- If all required parameters are already provided, You MUST proceed to the Steps
- If any required parameters are missing, You MUST ask for them before proceeding
- When asking for parameters, You MUST request all parameters in a single prompt
- When asking for parameters, You MUST use the exact parameter names as defined

## Steps
### 1. Initialize or resume the kit
Inspect existing state before starting `pipeline-prop-kit`.

**Constraints:**
- You MUST run `gamedev status`, `gamedev doctor`, and `gamedev resume` when a session exists.
- You MUST NOT start a duplicate kit because duplicate asset ids and outputs would conflict.
- You MUST persist the exact prop list and acceptance criteria in session state.

### 2. Freeze the shared contract
Dispatch kit planning and external research to `project-manager` and `asset-researcher`.

**Constraints:**
- You MUST assign one manifest id, dimensions, budget, material family, and output path per prop.
- You MUST define shared texel density, pivot rules, LOD policy, and target Unity pipeline.
- You MUST block unverified external sources at `license-compliance`.

### 3. Produce geometry
Dispatch blockout and final geometry batches to `blender-modeler`.

**Constraints:**
- You SHOULD process independent props in batches no larger than four concurrent subagents.
- You MUST require the same contract for every batch.
- You MUST validate identity, dimensions, silhouette, and budget before materials.
- You MUST persist results by asset id rather than summarizing them only in context.

### 4. Produce materials and UVs
Dispatch validated geometry to `blender-materials`.

**Constraints:**
- You MUST apply the shared material family and texel-density policy.
- You MUST record all texture provenance and license evidence.
- You MUST return per-asset validation results so one failure cannot hide in an aggregate pass.

### 5. Optimize and export
Dispatch each complete asset to `blender-exporter`.

**Constraints:**
- You MUST enforce license, transform, origin, naming, poly, and material-slot gates.
- You MUST request approval for each existing destination before overwrite.
- You MUST record one export path and checksum per manifest asset.

### 6. Build prefab batch
Dispatch imports and prefabs to `unity-scene-builder`, then physics to `unity-physics-engineer`.

**Constraints:**
- You MUST create one stable prefab per manifest asset.
- You MUST use simple colliders that match each prop's static or dynamic role.
- You MUST place every prefab in one deterministic validation scene.

### 7. Validate the kit
Dispatch the validation scene and frozen criteria to `unity-qa-tester`.

**Constraints:**
- You MUST check every expected asset id exactly once.
- You MUST report missing assets, duplicate prefabs, console failures, collider issues, and budget regressions.
- If any prop fails, You MUST route only that defect to its owning specialist and repeat affected checks.

### 8. Prepare release
Dispatch the complete kit to `release-engineer`.

**Constraints:**
- You MUST verify manifest completeness, checksums, Unity metadata, LFS, generated-file exclusions, and QA evidence.
- You MUST request human approval before staging or committing.
- You MUST complete the final stage only after the `pipeline.stage` approval is consumed.

## Examples

### Ten forest props
**Input:**
- project_root: `/projects/forest-game`
- kit_brief: `Ten stylized forest props sharing one material family and three LOD bands`
- actor: `developer`

**Expected behavior:** Independent props may run in bounded parallel batches, but each retains its own manifest, export, prefab, and QA evidence.

## Troubleshooting

### One prop repeatedly fails
Block only the affected batch item, preserve passing items, and return the exact validation failure to its owning agent.

### Inconsistent kit output
Recheck the frozen shared contract before allowing additional local exceptions.
