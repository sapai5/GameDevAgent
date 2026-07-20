# Task execution policy

## Status

Accepted for [issue #65](https://github.com/sapai5/GameDevAgent/issues/65). The executable source of truth is `src/gamedev_agent/task_difficulty.py`; this document explains that policy and MUST change with its behavior and tests.

## Decision

Python classifies every `gamedev run` request before agent execution. Classification is deterministic and based on normalized request text plus explicit task state. It does not use an opaque model self-rating.

The preflight result is a schema-versioned contract containing:

- normalized request and state fingerprint
- difficulty and ordered score factors
- execution route
- allowed and skipped stages
- target properties for bounded edits
- required safety gates
- active, startup, queue, deadline, and per-stage budget evidence

The project-manager agent follows this contract but does not own or duplicate its policy. For mutations, the preflight also declares an initial change-domain write set; observed tool fingerprints are reconciled by the separate [change-impact validation policy](change-impact-validation.md) before validation evidence can pass.

## Difficulty classification

| Difficulty | Score | Default active-time budget | Typical work |
|---|---:|---:|---|
| Trivial | 0–1 | 60 seconds | Read/query or one bounded property edit |
| Small | 2–4 | 3 minutes | Several local edits with targeted checks |
| Standard | 5–12 | 10 minutes | Multi-object or multi-stage work |
| Complex | 13 or more | Per-stage estimates | Generation, simulation, final render, or broad composition |

Classification factors are additive and emitted with explanations.

| Factor | Points | Meaning |
|---|---:|---|
| Read-only query | 0 | No mutation requested |
| Bounded property edit | 1 | One existing target and one related property group |
| Local edits | 3 | Several local mutations require checks |
| Multi-object | 4 | Coordinated work across several objects |
| Unspecified work | 5 | Request is not bounded enough for a fast path |
| High density | 6 | Content density increases execution cost |
| Broad validation | 6 | Validation exceeds targeted checks |
| Multi-stage | 7 | Request crosses execution stages |
| Broad composition | 13 | Composition requires preview checkpoints |
| Generation | 13 | Generation requires preview checkpoints |
| Simulation | 14 | Simulation requires an estimated stage |
| Final render | 14 | Final rendering is an expensive stage |

Request normalization folds case and repeated whitespace. State inputs normalize connected application names and reject negative or non-finite timing estimates. Repeated classification of the same normalized request and state produces the same result and SHA-256 state fingerprint.

## Execution routes

| Route | Selection | Behavior |
|---|---|---|
| Query | Read-only request | Inspect authoritative state and report without mutation |
| Property edit | One bounded property group on an existing target | Inspect, evaluate safety, mutate only named properties, verify those properties, and persist applicable state evidence |
| Staged edit | Mutation without generation or simulation | Use a targeted local plan for Small or Standard work; use estimates, a preview checkpoint, and broad validation for Complex final-render or composition work |
| Rebuild | Generation or simulation | Estimate stages, create a preview checkpoint, execute only the requested generation or simulation stages, run broad validation, and persist state |

An explicitly requested pipeline takes precedence over fast-path pipeline avoidance. Otherwise, query and property-edit routes do not start or advance a broad persistent pipeline.

## Budget accounting

Active execution time excludes queue delay and cold application startup:

```text
wall time = queue delay + startup time + active execution time
```

A budget overrun compares actual active time with the effective active limit. Evidence retains the independent stage-based prediction, effective limit, actual active time, startup time, queue time, wall time, and any per-stage overruns.

Complex work has no fixed default active limit. Its initial stage estimates are:

| Stage | Active-time estimate |
|---|---:|
| Plan with estimates | 60 seconds |
| Evaluate safety gates | 30 seconds |
| Preview checkpoint | 3 minutes |
| Generation | 10 minutes |
| Simulation | 10 minutes |
| Final render | 15 minutes |
| Export | 2 minutes |
| Broad validation | 5 minutes |
| Persist authoritative state | 30 seconds |

Only selected stages contribute to a Complex prediction. A user deadline sets the effective active limit but does not erase the original prediction or authorize skipped safety work.

## User overrides

Explicit user controls win over inferred presentation and scheduling policy:

- `brief` or `--detail brief` requests concise evidence.
- `detailed` or `--detail detailed` requests expanded evidence.
- `do not render`, `without rendering`, or `--no-render` forbids preview and final render stages.
- Text such as `within 60 seconds` or `--deadline-seconds 60` sets an active-time deadline.

When request text and CLI options conflict, the explicit CLI option wins. Overrides never bypass safety gates.

## Bounded property fast path

Changing an existing warm Blender scene from 4K to 2K is the motivating fast path. The classifier targets only:

```text
blender.scene.render.resolution_x
blender.scene.render.resolution_y
```

The allowed stages are:

1. Inspect the target.
2. Evaluate applicable safety gates.
3. Mutate the named properties.
4. Verify the targeted properties.
5. Persist applicable authoritative-state evidence.

The route explicitly skips generation, simulation, preview rendering, final rendering, export, and broad validation. Its default active-time budget is 60 seconds. Blender startup and queue delay remain separate from that limit.

## Safety invariants

Every route retains these safety gates:

- license integrity
- provenance integrity
- spatial integrity
- required approvals
- authoritative-state integrity

A gate can be inapplicable to a mutation, but it cannot be removed or treated as passed merely to satisfy a route, detail preference, or deadline. Destructive operations and overwrites continue to use one-time approvals.

## Audit evidence

`gamedev run` writes a `task-preflight-classified` event to `logs/audit.jsonl` before starting an agent. The event includes the complete serialized assessment. Budget evaluation evidence uses the `task-budget-evaluated` event shape with predicted, limited, and actual timing fields.

## Validation

The policy requires tests for:

- deterministic normalization and fingerprints
- every difficulty and route
- override precedence
- invalid, negative, and non-finite timing inputs
- stage pruning for the warm 4K-to-2K edit
- startup and queue separation
- predicted-versus-actual overrun evidence
- safety-gate retention
- CLI audit and prompt routing

Run:

```bash
PYTHONPATH=src python -m unittest tests.test_task_difficulty -v
PYTHONPATH=src python -m unittest discover -s tests -v
```
