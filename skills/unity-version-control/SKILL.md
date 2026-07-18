---
name: unity-version-control
description: Defines Unity text serialization, visible metadata, Git LFS, ignore rules, and YAML conflict handling. Use when initializing or releasing a Unity project.
tags: [unity, git, lfs]
---

# Unity Version Control

## Overview
Keep Unity projects reviewable and recoverable by versioning source assets and metadata while excluding generated caches and builds.

## Usage
Use this skill when:
- Creating `.gitignore`, `.gitattributes`, or Git LFS policy
- Reviewing a Unity change before commit
- Resolving scene, prefab, or metadata conflicts

## Core Concepts
- Visible `.meta` files preserve GUID references.
- Force Text serialization enables review and merge tooling.
- Large binary source assets belong in LFS according to repository policy.

## Workflow
1. You MUST enable visible metadata and text serialization in the Unity project.
2. You MUST track every source asset with its `.meta` file.
3. You MUST ignore Library, Temp, Logs, Obj, Builds, and user-local settings.
4. You SHOULD track large binary art, audio, and media patterns with LFS after confirming team policy.
5. You MUST resolve YAML conflicts semantically and reopen affected assets in Unity.

## Example
Track `.blend`, `.fbx`, `.psd`, and large audio through LFS while committing scenes, prefabs, scripts, settings, and all corresponding metadata.

## Validation
You MUST inspect status, LFS tracking, missing metadata, generated files, and Unity console state before release.
