---
name: naming-and-conventions
description: Defines shared asset ids, prefixes, paths, versions, and taxonomy across Blender, Unity, manifests, logs, and pipelines. Use before naming any project artifact.
tags: [naming, taxonomy, conventions]
---

# Naming and Conventions

## Overview
Use one stable identity across source files, exports, Unity assets, prefabs, logs, and manifest records.

## Usage
Use this skill when:
- Creating an asset id, object, material, scene, prefab, script, or output path
- Handing work between Blender and Unity agents
- Reviewing inconsistent names or duplicate ownership

## Core Concepts
- The manifest asset id is stable; display names MAY change.
- Prefixes communicate artifact role, not arbitrary style.
- Paths communicate ownership and lifecycle, while names communicate identity.

## Workflow
1. You MUST assign a lowercase kebab-case manifest id such as `forest-crate-a`.
2. You MUST derive tool names consistently, such as `SM_ForestCrate_A` and `PF_ForestCrate_A`.
3. You MUST use role prefixes documented by the project: `SM`, `SK`, `COL`, `MAT`, `T`, `PF`, and `SCN`.
4. You SHOULD use explicit variants rather than suffixes such as `final` or `new`.
5. You MUST check the manifest before creating a new identity.

## Example
Manifest `forest-crate-a` maps to Blender `SM_ForestCrate_A`, export `SM_ForestCrate_A.glb`, and Unity prefab `PF_ForestCrate_A.prefab`.

## Validation
You MUST verify uniqueness, stable casing, role prefix, and matching manifest paths before handoff.
