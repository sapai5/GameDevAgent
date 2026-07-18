---
name: unity-prefab-workflow
description: Defines Unity prefab roots, nested prefabs, variants, overrides, and unpacking policy. Use when assembling reusable GameObjects from imported assets.
tags: [unity, prefabs, gameobjects]
---

# Unity Prefab Workflow

## Overview
Build reusable prefabs with explicit ownership, minimal overrides, and stable links to imported source assets.

## Usage
Use this skill when:
- Creating a new prefab or prefab variant
- Deciding between nesting, variants, duplication, or unpacking
- Reviewing unexpected overrides or broken references

## Core Concepts
- The prefab root expresses identity and lifecycle.
- Variants encode intentional differences; scene overrides are not a variant system.
- Unpacking severs inheritance and requires a documented reason.

## Workflow
1. You MUST assign one manifest asset or feature identity to the prefab root.
2. You SHOULD nest reusable components instead of duplicating their hierarchy.
3. You MUST apply or revert overrides intentionally before handoff.
4. You MUST NOT unpack a prefab because it destroys inheritance without an approved ownership change.
5. You MUST save prefabs at stable project paths.

## Example
`PF_Crate_A` nests the imported mesh child, collider child, and interaction component; `PF_Crate_A_Damaged` is a variant with documented overrides.

## Validation
You MUST reopen the prefab, inspect overrides and missing references, and instantiate it in a clean scene.
