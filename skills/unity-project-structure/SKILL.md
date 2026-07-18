---
name: unity-project-structure
description: Defines Unity Assets folder, package, assembly definition, editor, test, and generated-content boundaries. Use when creating or reorganizing Unity project content.
tags: [unity, structure, assemblies]
---

# Unity Project Structure

## Overview
Keep Unity source, imported assets, generated output, editor code, and tests in predictable ownership boundaries.

## Usage
Use this skill when:
- Creating a feature, package, scene, or asset folder
- Adding assembly definitions or tests
- Deciding whether generated content belongs in version control

## Core Concepts
- Feature ownership is clearer than folders grouped only by file type.
- Editor-only code and runtime code require separate compilation boundaries.
- Unity `.meta` files travel with their assets.

## Workflow
1. You MUST inspect existing conventions before adding folders.
2. You SHOULD group owned runtime content under a stable feature or project namespace.
3. You MUST separate Editor and test assemblies from runtime assemblies.
4. You MUST keep builds, caches, and transient imports outside versioned Assets.
5. You MUST move assets with their `.meta` files.

## Example
`Assets/Game/Interaction/{Runtime,Editor,Tests}` uses explicit assembly definitions and keeps imported art under `Assets/Game/Art/Imported`.

## Validation
You MUST trigger compilation and confirm no unintended assembly references or missing scripts.
