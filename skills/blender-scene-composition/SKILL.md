---
name: blender-scene-composition
description: Organizes Blender scene layout, collections, hierarchy, spatial rhythm, and shot readability. Use when assembling assets into a scene or level reference.
tags: [blender, composition, layout]
---

# Blender Scene Composition

## Overview
Arrange traceable assets into readable scenes while preserving collection ownership and export boundaries.

## Usage
Use this skill when:
- Blocking a level, diorama, product scene, or cinematic shot
- Creating collection and parent hierarchies
- Reviewing visual balance, scale cues, or camera readability

## Core Concepts
- Composition supports a focal path and gameplay or shot intent.
- Collections define ownership and export scope; they are not cosmetic folders.
- Linked or instanced assets preserve source identity better than untracked copies.

## Workflow
1. You MUST identify focal points, player or camera path, and scale references.
2. You MUST place assets by manifest id and preserve source object identity.
3. You SHOULD use instances for repeated assets unless unique editing is required.
4. You MUST keep export collections separate from helpers and references.
5. You MUST report missing assets or ambiguous ownership before handoff.

## Example
A forest path uses repeated rock instances to frame the route, one hero tree as a landmark, and a dedicated `EXPORT_Level_A` collection.

## Validation
You MUST inspect the hierarchy, viewport from required cameras, and collection export membership.
