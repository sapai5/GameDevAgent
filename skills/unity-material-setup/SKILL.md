---
name: unity-material-setup
description: Maps Blender PBR materials and textures to Unity Built-in, URP, or HDRP shaders. Use after model import or render-pipeline changes.
tags: [unity, materials, pbr]
---

# Unity Material Setup

## Overview
Translate portable PBR intent into the project's selected Unity render pipeline without losing texture semantics.

## Usage
Use this skill when:
- Remapping imported Blender materials
- Configuring normal, metallic, roughness, occlusion, emission, or transparency
- Migrating between Unity render pipelines

## Core Concepts
- Shader property names and mask packing differ by render pipeline.
- Roughness often maps to inverted smoothness and requires an explicit channel rule.
- Texture color space must match data semantics.

## Workflow
1. You MUST identify Built-in, URP, or HDRP before creating materials.
2. You MUST map each source channel to a documented target property and channel.
3. You MUST configure texture import color space and normal-map type.
4. You SHOULD create native Unity materials rather than depend on fragile embedded extraction.
5. You MUST preserve source texture license records.

## Example
For URP Lit, base color remains sRGB, normal is imported as Normal Map, metallic is non-color, and smoothness uses the project's documented alpha source.

## Validation
You MUST compare the Unity material under neutral lighting with the Blender validation render.
