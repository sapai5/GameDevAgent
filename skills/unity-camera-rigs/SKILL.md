---
name: unity-camera-rigs
description: Builds Unity camera rigs, follow/look behavior, clipping, damping, and transitions. Use for gameplay cameras or Blender camera handoff.
tags: [unity, camera, rigs]
---

# Unity Camera Rigs

## Overview
Create camera behavior with explicit targets, update timing, framing, and transition ownership.

## Usage
Use this skill when:
- Creating first-person, third-person, orbital, rail, or fixed cameras
- Importing camera framing from Blender
- Diagnosing jitter, clipping, target loss, or abrupt transitions

## Core Concepts
- Camera transform ownership must not compete with gameplay scripts.
- Follow updates should occur after target movement where appropriate.
- Focal length or field of view, aspect, and clipping define framing together.

## Workflow
1. You MUST define rig type, target, framing, occlusion, and transition requirements.
2. You MUST assign one system as final camera transform owner.
3. You SHOULD separate input intent, target tracking, and camera output.
4. You MUST handle missing or replaced targets without exceptions.
5. You MUST verify clipping and framing at supported aspect ratios.

## Example
A third-person rig follows a target pivot in late update, consumes look intent, and applies bounded collision pull-in.

## Validation
You MUST test stationary and fast targets, obstruction, target replacement, scene reload, and aspect changes.
