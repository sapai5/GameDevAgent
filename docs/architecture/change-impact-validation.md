# Change-impact validation routing

Impact plans are derived and rebuildable; `state/manifest.json` and session JSON remain authoritative.

## Contract

Every planned mutation declares a bounded write set using schema version 1. Tool results then report the observed domains and a lowercase SHA-256 before/after fingerprint for every tracked domain:

- geometry/topology
- object transforms
- camera
- lighting/world
- materials/textures
- animation
- render settings
- export/import
- provenance/license
- authoritative state

`gamedev run` includes the inferred initial declaration in its existing task preflight. Before validation, the project manager supplies actual observations to:

```bash
gamedev impact plan --input impact-request.json
```

The input can use `-` for stdin. The CLI emits canonical JSON and appends a `change-impact-planned` audit record.

## Reconciliation

A ready plan requires all of the following:

1. The declared and observed domain sets match.
2. The observed set exactly matches domains whose before and after fingerprints differ.
3. Every tracked domain has a fingerprint, including unchanged domains used to justify skipped checks.
4. No declaration or observation uses `unknown`.

Missing, unknown, or conflicting evidence produces a `blocked` plan. A blocked plan selects only inspection, safety evaluation, and conservative validation; it does not select mutation or persistence. Prior evidence is invalidated and cannot yield PASS. A cancelled plan retains the logical selection and audit reasons but schedules no dirty nodes.

## Initial routes

| Changed domain | Selected validation | Important exclusions |
|---|---|---|
| Render settings | Exact render-setting verification | Generation, render, export, and spatial validation |
| Lighting/world | Color, exposure, clipping, render-state, and configured visual checks | Geometry generation and spatial validation |
| Camera | Composition and terrain-relative clearance | Geometry, topology, material, and broad spatial regeneration |
| Geometry/topology | Grounding, penetration, bounds, topology | Unrelated material and animation checks |
| Object transforms | Grounding, penetration, and bounds | Topology unless geometry also changed |
| Materials/textures | Material, texture, and configured visual checks | Topology unless geometry also changed |
| Animation | Channels, frame range, continuity, and dependent render evidence | Geometry and material checks |
| Export/import | Export/import verification and export stage | Unrelated scene checks |
| Provenance/license | Provenance and license validation | Unrelated content checks |
| Authoritative state | State-integrity validation and persistence | Unrelated content checks |

All mutation plans retain license, provenance, spatial, approval, and authoritative-state safety gates. A gate may be inapplicable only when the complete unchanged-domain fingerprint set supports that decision.

## Invalidation graph

The plan emits:

- selected and skipped stages or validators, each with a machine-readable reason, input fingerprint, dependency list, and supporting domain fingerprints
- selected dependency edges
- exact invalidated validators, render caches, export artifacts, and caller-supplied downstream DAG nodes
- dirty nodes to execute
- checksum-matched PASS evidence that can be reused
- status and reconciliation reason codes

Geometry, transform, material, and animation changes invalidate downstream export evidence. Scene-visible changes invalidate relevant render evidence. Caller-supplied artifact graphs are validated as DAGs; dirty seeds propagate once through outgoing edges. Duplicate identifiers, missing nodes, self-edges, and cycles are rejected.

On resume, reusable validators are removed from the dirty and invalidated sets only when their node ID, expected input fingerprint, and PASS outcome all match. Failed, stale, or mismatched evidence reruns. This keeps the graph derived while authoritative state remains in the manifest and session stores.

## Determinism and limits

Inputs are normalized into immutable enums and sorted tuples. Plans serialize with sorted keys and compact separators, and include a checksum over the complete plan body. Identical normalized evidence produces byte-identical output.

The planner accepts at most 4 MiB of JSON per request. Tests cover a 1,000-artifact, 10,000-edge acyclic graph and enforce a 100 ms p95 planning ceiling after warm-up.

## Validation

Run:

```bash
PYTHONPATH=src python -m unittest tests.test_change_impact -v
PYTHONPATH=src python -m unittest tests.test_task_difficulty -v
PYTHONPATH=src python -m unittest tests.test_pipeline_cli -v
PYTHONPATH=src python -m unittest discover -s tests -v
```
