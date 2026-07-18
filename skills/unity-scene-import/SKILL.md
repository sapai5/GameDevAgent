---
name: unity-scene-import
description: Imports traceable Blender exports into Unity with stable model, rig, animation, and material settings. Use when a manifest asset enters Unity.
tags: [unity, import, assets]
---

# Unity Scene Import

## Overview
Import only manifest-tracked artifacts and make every model importer choice reproducible.

## Usage
Use this skill when:
- Importing glTF, GLB, FBX, textures, or animation clips
- Repairing scale, normals, materials, rig, or clip settings
- Reimporting after a Blender source change

## Core Concepts
- The manifest export path and checksum identify the handoff artifact.
- Importer settings are Unity-side source configuration, not manual scene fixes.
- Reimport must preserve prefab references and stable asset paths.

## Workflow
1. You MUST verify license state, export path, and checksum before import.
2. You MUST place the artifact under the agreed imported-art boundary.
3. You MUST configure scale, normals, materials, rig, and clips explicitly.
4. You MUST compare bounds and orientation with the source contract.
5. You MUST record the Unity import path in the manifest.

## Example
Import `Exports/Props/SM_Crate_A.glb` to `Assets/Game/Art/Imported/Props/SM_Crate_A.glb` and verify one-meter bounds.

## Validation
You MUST inspect console output, imported hierarchy, materials, animation clips, and checksum linkage.
