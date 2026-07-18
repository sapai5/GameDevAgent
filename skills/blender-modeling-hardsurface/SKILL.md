---
name: blender-modeling-hardsurface
description: Guides non-destructive hard-surface Blender modeling with clean topology and modifier discipline. Use for props, architecture, machines, and modular kits.
tags: [blender, modeling, hard-surface]
---

# Blender Modeling Hardsurface

## Overview
Build readable, editable hard-surface assets that satisfy the assigned silhouette and polygon budget.

## Usage
Use this skill when:
- Blocking out or finishing rigid props and modular environment pieces
- Choosing bevel, boolean, mirror, or weighted-normal workflows
- Reviewing topology before UV or export work

## Core Concepts
- Silhouette and shading quality determine where geometry is valuable.
- Modifier order is part of the model and MUST remain intentional.
- Non-destructive sources and export meshes MAY differ but require traceable names.

## Workflow
1. You MUST confirm dimensions, viewing distance, and triangle budget.
2. You MUST establish the primary silhouette before secondary detail.
3. You SHOULD use modifiers for repeatable operations and name important modifiers.
4. You MUST inspect normals, non-manifold edges, ngons on deforming surfaces, and hidden interior faces.
5. You MUST hand off without materials or export changes outside this skill's scope.

## Example
For a sci-fi crate, block the one-meter silhouette, mirror symmetric structure, bevel only visible hard edges, and reserve small panel detail for normal maps.

## Validation
You MUST compare final dimensions and evaluated triangle count with the asset contract.
