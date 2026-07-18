---
name: blender-spatial-placement
description: Measures and corrects Blender terrain contact, support anchors, hierarchy transforms, floating or buried meshes, rock burial, and terrain-relative camera clearance. Use when placing trees, rocks, props, cameras, or collection instances on uneven ground, or when a visual placement claim needs deterministic validation.
tags: [blender, placement, terrain, raycast, validation]
---

# Blender Spatial Placement

## Overview
Use evaluated world-space geometry and vertical support raycasts to place objects deterministically. Object origins and nominal Z coordinates are metadata, not evidence of contact.

## Usage
Use this skill when:
- Grounding trees, rocks, props, or collection instances on terrain
- Correcting hierarchy transforms without separating child meshes
- Setting camera height relative to local terrain
- Validating penetration, floating distance, support anchors, or export pivots
- Investigating a screenshot that disagrees with a prior numeric pass

Run `scripts/validate_spatial.py` inside Blender through a narrowly approved Blender code-execution tool. The script imports only Blender's `bpy` and `mathutils` modules plus Python's standard `json` module, makes no scene mutations, and returns structured JSON.

## Core Concepts
- You MUST measure evaluated mesh vertices in world space because modifiers, parents, and instances can invalidate source coordinates.
- You MUST raycast vertically at the measured contact X/Y because world Z alone does not describe uneven terrain.
- You MUST prefer an explicit contact mesh or anchor contract because an object origin may be above, below, or beside visible geometry.
- You MUST move the placement root while preserving child transforms because moving only a trunk or rock mesh can break the asset hierarchy.
- You MUST report `BLOCKED` when contact geometry, terrain hits, or instance identity cannot be measured because missing evidence is not a pass.
- You MUST treat disagreement between numeric and visual evidence as `FAIL` or `BLOCKED` because either the measurement target or the evidence is incomplete.

## Workflow
Copy this checklist and track each assigned object separately:

- [ ] Record the terrain or support surface, placement root, and explicit contact mesh names.
- [ ] Evaluate contact geometry and hierarchy transforms in world space.
- [ ] Raycast local terrain at each measured contact point.
- [ ] Compare measured penetration, floating distance, burial fraction, or camera clearance with the declared tolerance.
- [ ] Correct the placement root, not decorative children, then reevaluate the dependency graph.
- [ ] Rerun the deterministic script and capture its JSON result.
- [ ] Capture a side or below-grade view that exposes terrain thickness and possible penetration.
- [ ] Return one row per object with measured values and `PASS`, `FAIL`, or `BLOCKED`.

Proceed to correction only after every target has a measurable contact contract. Proceed to handoff only after the rerun and side-view evidence agree.

## Tolerances
Tolerances are acceptance criteria, not hidden constants. You MUST pass them explicitly when project requirements differ.

- Tree trunks SHOULD embed between `0.02` and `0.05` meters so small terrain variation does not create visible gaps without hiding substantial trunk length.
- Rocks SHOULD declare a burial fraction appropriate to their silhouette; `0.02` to `0.35` is the general-purpose default range.
- Human-eye cameras SHOULD declare terrain-relative clearance, commonly `1.6` to `1.8` meters. Aerial or stylized cameras MUST use their own stated range.
- Exportable props SHOULD validate their explicit support geometry against the intended local support plane, commonly world Z `0`, before export.

## Deterministic Validator
Load the script and call `run_from_json` from Blender:

```python
import json

namespace = {}
script = "/absolute/project/skills/blender-spatial-placement/scripts/validate_spatial.py"
exec(compile(open(script, encoding="utf-8").read(), script, "exec"), namespace)
config = {
    "terrain_name": "Terrain",
    "trees": [
        {
            "name": "Tree_01",
            "contact_objects": ["Tree_01_Trunk"],
            "min_embed_m": 0.02,
            "max_embed_m": 0.05,
        }
    ],
    "rocks": [
        {
            "name": "Rock_01",
            "objects": ["Rock_01"],
            "min_burial_fraction": 0.02,
            "max_burial_fraction": 0.35,
        }
    ],
    "cameras": [
        {"name": "Camera", "min_clearance_m": 1.6, "max_clearance_m": 1.8}
    ],
}
print(namespace["run_from_json"](json.dumps(config)))
```

For a prop kit without terrain, supply `supports` entries with `objects`, `surface_z`, `min_embed_m`, and `max_embed_m`. For collection instances, also supply `instance_root`; the validator matches evaluated instance geometry instead of assuming the source object's transform.

## Correction Rules
1. You MUST identify the placement root and contact geometry before calculating an offset.
2. You MUST calculate the correction from measured contact Z and raycast support Z.
3. You MUST apply the offset to the placement root and preserve orientation and scale.
4. You MUST reevaluate geometry after every correction because dependency-graph output can change.
5. You MUST stop after a bounded correction attempt and report the remaining numeric error if the tolerance still fails.

Proceed to validation after correction. Return to contact-contract discovery if the measured geometry changes or the validator reports `BLOCKED`.

## Output
Return a dense table with these columns:

| Target | Kind | Support Z | Contact or eye Z | Penetration / clearance | Tolerance | Result |
|---|---|---:|---:|---:|---|---|
| Tree_01 | tree | 0.842 m | 0.812 m | 0.030 m penetration | 0.020–0.050 m | PASS |
| Camera | camera | 1.134 m | 0.720 m | -0.414 m clearance | 1.600–1.800 m | FAIL |

A summary MUST NOT replace per-target rows because aggregate results can hide one deeply buried trunk.

## Validation
- You MUST run the script after the final transform change and preserve its JSON output.
- You MUST require all assigned targets to return `PASS`; `BLOCKED` is not success.
- You MUST inspect a side or below-grade view because a top view can hide deep penetration.
- You MUST rerun validation after composition or camera changes because later transforms can invalidate earlier evidence.
