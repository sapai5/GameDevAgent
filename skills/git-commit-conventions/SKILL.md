---
name: git-commit-conventions
description: Defines focused, validated Git commits for completed game-development units. Use after a pipeline stage passes QA and before release history changes.
tags: [git, commits, release]
---

# Git Commit Conventions

## Overview
Create reviewable history only from validated, related files with an imperative Conventional Commit message.

## Usage
Use this skill when:
- Preparing a commit after a completed pipeline unit
- Reviewing staged Unity, Blender, manifest, or agent changes
- Separating unrelated work before release

## Core Concepts
- A commit represents one completed, tested unit of behavior or content.
- Generated outputs, local state, and caches do not belong in source history.
- Git mutations require explicit human approval in this repository.

## Workflow
1. You MUST inspect status and diff before staging.
2. You MUST verify tests, QA evidence, manifest checksums, metadata, ignore rules, and LFS policy.
3. You MUST stage explicit related paths rather than all workspace changes.
4. You MUST use an imperative Conventional Commit subject that explains the unit.
5. You MUST NOT bypass hooks or rewrite shared history because doing so removes safety evidence.

## Example
`feat(props): Add forest crate kit` includes source assets, exports, Unity prefabs and metadata, manifest records, and the QA report for that kit.

## Validation
You MUST show the staged diff and exact proposed message before requesting commit approval.
