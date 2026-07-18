---
name: blender-lighting-camera
description: Defines Blender lighting rigs, exposure checks, cameras, and shot framing. Use for scene presentation, look development, or camera handoff.
tags: [blender, lighting, camera]
---

# Blender Lighting Camera

## Overview
Create intentional, reproducible lighting and camera setups without hiding material or scale defects.

## Usage
Use this skill when:
- Establishing neutral look-development lighting
- Framing a scene, product shot, or level reference camera
- Diagnosing exposure, clipping, or inconsistent light scale

## Core Concepts
- A neutral validation rig and an artistic rig serve different purposes.
- Focal length, sensor, clipping planes, and transform form the camera contract.
- Light size controls softness; intensity must be evaluated with exposure.

## Workflow
1. You MUST identify whether the rig is validation or artistic lighting.
2. You MUST set camera focal length, framing, and clipping planes deliberately.
3. You SHOULD separate key, fill, rim, and environment contributions for diagnosis.
4. You MUST inspect highlight clipping and shadow readability.
5. You MUST name cameras and lights using the shared taxonomy.

## Example
A validation rig uses a neutral environment, broad key, weak fill, and fixed camera so material revisions can be compared consistently.

## Validation
You MUST render or capture the assigned camera and report exposure, resolution, and any clipped geometry.
