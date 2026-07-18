---
name: blender-uv-unwrapping
description: Guides Blender seam placement, UV unwrap, texel density, overlap policy, and lightmap readiness. Use before texture assignment or export.
tags: [blender, uv, textures]
---

# Blender UV Unwrapping

## Overview
Produce UV layouts that match the asset's texturing method, texel-density target, and lightmap needs.

## Usage
Use this skill when:
- Unwrapping a new mesh or repairing stretched islands
- Standardizing texel density across a prop kit
- Creating a separate non-overlapping lightmap UV set

## Core Concepts
- Seams trade visibility for lower distortion.
- Intentional mirrored overlap differs from accidental overlap.
- Padding is measured for the target texture resolution and mip behavior.

## Workflow
1. You MUST apply or account for object scale before unwrap.
2. You MUST place seams on hidden or natural boundaries where practical.
3. You MUST set and verify the project texel-density target.
4. You MUST identify every overlap as intentional or erroneous.
5. You SHOULD create a separate lightmap channel when static baked lighting requires it.

## Example
A wooden crate separates lid, body, and underside islands; mirrored metal brackets may overlap only when directional detail is not required.

## Validation
You MUST inspect a checker texture, island bounds, overlap report, and padding at target resolution.
