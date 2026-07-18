---
name: unity-performance-profiling
description: Profiles Unity CPU, GPU, memory, rendering, physics, and loading against explicit budgets. Use when validating a slice or investigating regressions.
tags: [unity, profiling, performance]
---

# Unity Performance Profiling

## Overview
Measure representative builds before optimizing and tie every change to a named budget and captured evidence.

## Usage
Use this skill when:
- Establishing frame, memory, draw-call, or loading baselines
- Investigating spikes, allocations, overdraw, or physics cost
- Validating asset and build optimization work

## Core Concepts
- Editor measurements include noise; target-device development builds are stronger evidence.
- Averages hide spikes, so representative frame distributions matter.
- CPU, GPU, memory, and I/O bottlenecks require different remedies.

## Workflow
1. You MUST define target hardware, scenario, duration, and budgets.
2. You MUST capture a baseline before making optimization changes.
3. You MUST identify the dominant bottleneck using profiler evidence.
4. You SHOULD change one cost driver at a time and recapture the same scenario.
5. You MUST reject improvements that break visual or gameplay acceptance criteria.

## Example
Profile a 60-second prop-kit scene, record main-thread frame time, batches, triangles, and memory, then compare the same camera path after LOD changes.

## Validation
You MUST save before-and-after metrics and state whether each budget passed.
