---
name: unity-build-settings
description: Configures Unity scenes, player settings, target platform, backend, quality, and reproducible build output. Use before development or release builds.
tags: [unity, build, platform]
---

# Unity Build Settings

## Overview
Produce reproducible builds from explicit scene, platform, player, quality, and output contracts.

## Usage
Use this skill when:
- Adding scenes to a build or changing target platform
- Configuring development, profiling, or release outputs
- Diagnosing build-time errors or platform-specific settings

## Core Concepts
- Build scene order can be runtime behavior.
- Player settings and scripting backend are release inputs.
- Build directories are generated artifacts and require overwrite approval.

## Workflow
1. You MUST identify target platform, build purpose, scene list, and output path.
2. You MUST verify product identity, version inputs, backend, architecture, and API compatibility.
3. You MUST select quality and render settings for the target.
4. You MUST NOT overwrite an existing build because prior validation evidence would be lost without explicit approval.
5. You MUST capture build result, warnings, size, and duration.

## Example
A development build includes the bootstrap and test level scenes, enables script debugging only when requested, and writes to a unique output directory.

## Validation
You MUST launch the built player, execute a smoke path, and inspect player logs.
