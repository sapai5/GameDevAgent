---
name: blender-materials-pbr
description: Creates portable Blender PBR materials and texture assignments. Use for Principled BSDF authoring destined for Unity render pipelines.
tags: [blender, pbr, materials]
---

# Blender Materials PBR

## Overview
Author physically plausible, portable materials with explicit texture provenance and color-space settings.

## Usage
Use this skill when:
- Creating or auditing Principled BSDF materials
- Assigning base color, normal, roughness, metallic, or occlusion maps
- Preparing materials for Unity remapping

## Core Concepts
- Base color is color data; mask, roughness, metallic, and normal maps are non-color data.
- Material names and texture paths are stable handoff identifiers.
- Texture license and source records belong in the manifest.

## Workflow
1. You MUST confirm the target Unity render pipeline and texture budget.
2. You MUST use a Principled BSDF-centered graph unless the handoff contract documents an exception.
3. You MUST set each image's color space according to its data role.
4. You SHOULD pack channels only when the Unity material skill defines the mapping.
5. You MUST report all external textures and their manifest records.

## Example
`MAT_MetalPaint_A` connects sRGB base color, non-color metallic and roughness masks, and a non-color normal map through a Normal Map node.

## Validation
You MUST inspect the material under neutral lighting and verify missing-file and unsupported-node warnings are absent.
