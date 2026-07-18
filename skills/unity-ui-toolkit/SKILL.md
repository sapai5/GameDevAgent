---
name: unity-ui-toolkit
description: Builds Unity UI Toolkit documents, USS, binding, navigation, HUDs, and menus. Use for runtime UI or editor-style interfaces.
tags: [unity, ui-toolkit, ui]
---

# Unity UI Toolkit

## Overview
Create maintainable UI with separated structure, style, presentation state, and gameplay events.

## Usage
Use this skill when:
- Building HUD, menu, pause, settings, or results screens
- Adding keyboard or gamepad navigation
- Diagnosing layout, binding, focus, or scaling behavior

## Core Concepts
- UXML owns structure, USS owns presentation, and C# owns behavior and binding.
- UI consumes stable state and emits intent; it should not own game rules.
- Focus order and readable scaling are functional requirements.

## Workflow
1. You MUST define screens, state inputs, user actions, and supported resolutions.
2. You MUST use shared USS classes and variables for repeated design tokens.
3. You SHOULD bind through a presenter or view model rather than scene searches.
4. You MUST implement keyboard and controller focus when those devices are supported.
5. You MUST unsubscribe events when the document is disabled or destroyed.

## Example
A pause document binds volume state, emits resume and quit intent, and restores the prior focus element when reopened.

## Validation
You MUST test supported resolutions, focus traversal, repeated enable cycles, missing data, and play-mode console output.
