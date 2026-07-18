---
name: license-compliance
description: Verifies asset and library licenses, attribution, redistribution, modification, and compatibility before import or release. Use as the manifest license gate.
tags: [license, compliance, provenance]
---

# License Compliance

## Overview
Block unverified external content from downstream pipelines and preserve the evidence needed to satisfy license obligations.

## Usage
Use this skill when:
- Adding or updating an external asset, texture, audio file, package, or library
- Preparing Blender export, Unity import, or release
- A source lacks a clear license or attribution record

## Core Concepts
- A download page claim is not a license text when the project provides a canonical license file.
- License obligations can differ for source, compiled libraries, and distributed game assets.
- Unknown or conflicting terms remain blocked until a human resolves them.

## Workflow
1. You MUST identify the exact asset version and canonical license text.
2. You MUST record SPDX id or `LicenseRef-*`, source URL, license URL, and required notices.
3. You MUST evaluate modification, attribution, redistribution, commercial-use, and share-alike conditions.
4. You MUST NOT mark a license verified because missing evidence could create distribution risk.
5. You MUST update the manifest verifier and timestamp only after all checks pass.

## Example
A CC-BY asset records author, source, license URL, modifications, and the exact credit line included with the game.

## Validation
You MUST fail the gate when any asset has `verified: false`, an ambiguous version, or missing required notice.
