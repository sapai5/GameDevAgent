---
name: unity-physics-setup
description: Configures stable Unity colliders, rigidbodies, layers, collision matrices, and character movement. Use for physical interactions or collision debugging.
tags: [unity, physics, colliders]
---

# Unity Physics Setup

## Overview
Build stable, proportionate physics behavior with intentional body ownership and collision filtering.

## Usage
Use this skill when:
- Adding colliders, rigidbodies, triggers, or character controllers
- Configuring collision layers and matrices
- Diagnosing tunneling, jitter, unstable stacks, or expensive mesh collision

## Core Concepts
- A moving collider generally needs one owning Rigidbody in its hierarchy.
- Primitive and compound colliders are cheaper and often more stable than mesh colliders.
- Physics timestep and continuous collision settings solve different problems.

## Workflow
1. You MUST classify each object as static, kinematic, or dynamic.
2. You MUST choose the simplest collider that preserves gameplay behavior.
3. You MUST configure mass, constraints, interpolation, and collision detection intentionally.
4. You MUST update layers and the collision matrix with least interaction.
5. You MUST NOT use a dynamic non-convex MeshCollider because Unity cannot simulate it safely.

## Example
A movable crate uses one Rigidbody and compound BoxColliders; its visual mesh remains collider-free.

## Validation
You MUST test rest stability, high-speed collision, triggers, slopes, and representative frame cost.
