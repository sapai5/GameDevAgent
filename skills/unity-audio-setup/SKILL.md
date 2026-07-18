---
name: unity-audio-setup
description: Configures Unity audio clips, sources, mixers, spatial settings, and pooling. Use for effects, ambience, music, or UI feedback.
tags: [unity, audio, mixers]
---

# Unity Audio Setup

## Overview
Create predictable audio routing and playback with appropriate import, spatial, and concurrency settings.

## Usage
Use this skill when:
- Importing sound effects, ambience, voice, or music
- Creating AudioMixer groups and snapshots
- Diagnosing clipping, excessive voices, memory, or spatial behavior

## Core Concepts
- Import format and load type depend on clip length and reuse.
- Mixers centralize routing, volume, effects, and snapshots.
- Spatial blend, attenuation, and voice limits must match gameplay intent.

## Workflow
1. You MUST record audio source and license in the manifest.
2. You MUST choose compression, load type, sample settings, and mono conversion intentionally.
3. You MUST route sources through named mixer groups.
4. You SHOULD pool frequently repeated one-shot sources.
5. You MUST define concurrency or priority for repeatable effects.

## Example
Short impact clips decompress on load and use pooled 3D sources; streamed music routes through a Music mixer group.

## Validation
You MUST test mixer headroom, listener count, spatial falloff, rapid repetition, pause, and scene transitions.
