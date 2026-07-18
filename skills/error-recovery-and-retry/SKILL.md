---
name: error-recovery-and-retry
description: Handles Blender, Unity, web, and local MCP timeouts, disconnects, malformed responses, and partial work. Use whenever a tool call fails or an application is unavailable.
tags: [mcp, retry, recovery]
---

# Error Recovery and Retry

## Overview
Retry only transient, idempotent operations; persist partial progress and surface actionable blockers instead of repeating unsafe mutations.

## Usage
Use this skill when:
- Blender or Unity MCP is unreachable or times out
- A tool returns malformed JSON, application errors, or an uncertain mutation result
- A long-running pipeline is interrupted between stages

## Core Concepts
- Connectivity failures may be transient; validation and application errors are not fixed by blind retry.
- A timed-out mutation has uncertain outcome and requires inspection before repetition.
- Session state and audit logs are the recovery source of truth.

## Workflow
1. You MUST classify the failure as transient transport, deterministic request, application state, permission, or uncertain mutation.
2. You MAY retry an idempotent read up to the configured bounded attempt count with backoff.
3. You MUST inspect state before retrying a timed-out mutation.
4. You MUST NOT retry deletion, overwrite, export, or Git mutation blindly because duplicate execution can destroy data.
5. You MUST persist `blocked` or `failed` state with the error and the next safe action.

## Example
If `tools/list` times out, retry within policy; if an export call times out, inspect destination and checksum before deciding whether another export is safe.

## Validation
You MUST run `gamedev doctor`, confirm application state, and resume the existing session rather than starting a duplicate.
