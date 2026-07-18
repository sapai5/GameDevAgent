---
name: asset-research
description: Researches open-source 3D assets and game-development libraries with reproducible source evidence. Use when a project needs external art, tools, packages, or reference data.
tags: [assets, open-source, research]
---

# Asset Research

## Overview
Find the smallest suitable external dependency while preserving canonical source, version, integrity, and usage evidence.

## Usage
Use this skill when:
- Searching for 3D models, textures, audio, Unity packages, or tooling
- Comparing external libraries against project requirements
- Recording provenance before download or import

## Core Concepts
- Original project or publisher sources outrank mirrors and aggregators.
- Suitability includes format, render pipeline, maintenance, platform, and license.
- Research produces candidates; license compliance decides whether they may enter the project.

## Workflow
1. You MUST write required capabilities, excluded licenses, and technical constraints before searching.
2. You MUST inspect canonical project, release, documentation, and license sources.
3. You SHOULD compare at least two candidates when alternatives exist.
4. You MUST record source URL, version or commit, license claim, format, and compatibility risks.
5. You MUST pass the candidate to license compliance before download or import.

## Example
A tree asset candidate records its original repository, exact release tag, glTF contents, texture sizes, attribution file, and Unity pipeline notes.

## Validation
You MUST reopen every recorded source and distinguish verified facts from assumptions.
