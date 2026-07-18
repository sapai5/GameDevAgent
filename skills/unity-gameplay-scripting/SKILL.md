---
name: unity-gameplay-scripting
description: Guides focused, testable Unity C# gameplay components, state, events, and serialization. Use when implementing controllers, interactions, or game rules.
tags: [unity, csharp, gameplay]
---

# Unity Gameplay Scripting

## Overview
Implement bounded gameplay behavior with explicit dependencies, lifecycle ownership, and test seams.

## Usage
Use this skill when:
- Creating a player controller, interaction, state machine, or game rule
- Refactoring tightly coupled MonoBehaviours
- Adding EditMode or PlayMode tests for gameplay

## Core Concepts
- MonoBehaviours adapt Unity lifecycle events; domain logic can remain plain C#.
- Serialized dependencies should be validated before use.
- Events reduce direct coupling when ownership is clear.

## Workflow
1. You MUST define observable behavior and failure cases before writing code.
2. You MUST follow existing namespace, assembly, serialization, and test patterns.
3. You SHOULD isolate deterministic rules from frame and scene dependencies.
4. You MUST handle missing references and disabled lifecycle states explicitly.
5. You MUST add tests at the lowest sufficient Unity test level.

## Example
An interaction component detects an `IInteractable`, while a plain C# cooldown object owns timing rules and EditMode tests.

## Validation
You MUST compile, run targeted tests, enter play mode, and inspect the console for exceptions.
