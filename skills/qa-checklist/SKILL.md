---
name: qa-checklist
description: Defines deterministic Unity play-mode, console, asset, scene, input, physics, UI, build, and regression checks. Use for every QA stage and release gate.
tags: [qa, unity, regression]
---

# QA Checklist

## Overview
Return evidence-based pass or fail results against frozen acceptance criteria without silently fixing the system under test.

## Usage
Use this skill when:
- Validating an imported asset, prefab, scene, prop kit, or vertical slice
- Running Unity play-mode regression checks
- Preparing a pipeline stage or release for approval

## Core Concepts
- A pass requires evidence for every required check.
- Console errors and unhandled exceptions fail the run unless explicitly baselined.
- QA observations and implementation changes are separate units of work.

## Workflow
1. You MUST record Unity version, target scene or build, session id, and acceptance criteria.
2. You MUST clear the console, enter play mode, execute the prescribed path, and exit cleanly.
3. You MUST check missing references, errors, exceptions, input, physics, UI, audio, and scene transitions in scope.
4. You SHOULD capture performance metrics when the pipeline defines budgets.
5. You MUST report `PASS`, `FAIL`, or `BLOCKED` with reproduction steps and evidence.

## Example
A prop-kit run instantiates every prefab, checks collider stability, missing materials, console output, and asset bounds in one validation scene.

## Validation
You MUST fail rather than omit an inaccessible required check, and identify the blocker separately from product defects.
