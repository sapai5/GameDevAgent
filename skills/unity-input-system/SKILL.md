---
name: unity-input-system
description: Configures Unity Input System actions, maps, control schemes, rebinding, and lifecycle. Use for player controls or UI input.
tags: [unity, input-system, controls]
---

# Unity Input System

## Overview
Represent player intent as named actions decoupled from devices and gameplay implementations.

## Usage
Use this skill when:
- Adding movement, camera, interaction, menu, or rebinding controls
- Supporting keyboard, gamepad, touch, or multiple control schemes
- Diagnosing duplicate callbacks or disabled action maps

## Core Concepts
- Actions describe intent; bindings describe devices.
- Action map enablement belongs to a clear game or UI state owner.
- Generated wrappers provide safer identifiers than string lookup.

## Workflow
1. You MUST define actions, expected value types, and active game states.
2. You MUST add bindings and control schemes without embedding device checks in gameplay code.
3. You SHOULD use generated action wrappers where the project supports them.
4. You MUST subscribe and unsubscribe callbacks symmetrically.
5. You MUST validate keyboard and one alternate target control scheme when required.

## Example
`Gameplay/Move` emits a `Vector2`; the controller consumes intent, while movement physics remains owned by the physics component.

## Validation
You MUST test action-map transitions, device changes, canceled inputs, and rebinding persistence.
