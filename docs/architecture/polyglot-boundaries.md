# Polyglot architecture boundaries

## Status

Accepted as a foundation on `refactor/polyglot-architecture-foundation`. This change establishes optional boundaries without replacing existing Python behavior.

## Decision

GameDevAgent uses languages at stable system boundaries rather than assigning a different language to every concept.

| Boundary | Technology | Owns | Must not own |
|---|---|---|---|
| Control plane | Python 3.11+ | CLI, agents, pipelines, policy, MCP, providers, orchestration | Browser presentation or speculative performance kernels |
| Blender application | Python and `bpy` | Scene mutations and Blender-side deterministic validation | Cross-project policy or authoritative state |
| Derived AI memory | SQLite, SQL migrations, FTS5 | Documents, chunks, retrieval traces, graph projections, hardware samples | Authoritative asset/session state |
| Presentation | TypeScript | Future local dashboards, graph/retrieval visualization, approvals UI | Pipeline rules, license decisions, safety policy |
| Compute workers | Rust subprocesses | Profiled deterministic kernels with bounded JSONL requests | Orchestration, direct state mutation, hidden network access |
| Shared contracts | JSON Schema and fixtures | Versioned messages crossing language/process boundaries | Language-specific implementation details |

## Authority and data flow

`state/manifest.json`, session JSON, approvals, and audit JSONL remain authoritative. SQLite is derived, local memory and MUST be rebuildable from authoritative records or licensed source ingestion.

```text
TypeScript presentation
        ↕ versioned JSON envelopes
Python control plane ──→ SQLite/FTS5 derived memory
        ↕ versioned JSONL envelopes
bounded Rust workers
        ↕ MCP
Blender Python/bpy
```

No TypeScript or Rust component writes authoritative project state directly. Workers return evidence to Python, which validates it and decides whether to persist or apply it.

## Protocol

All process boundaries use the schema-versioned envelope in `src/gamedev_agent/contracts/envelope.schema.json`.

```json
{
  "schema_version": 1,
  "kind": "resource.estimate",
  "request_id": "request-123",
  "payload": {}
}
```

Messages are JSON objects, at most 1 MiB by default, and reject unknown envelope fields, unsupported versions, invalid kinds, non-finite numbers, and non-object payloads. Bulk geometry, images, and model files travel by project-relative path plus checksum rather than inline JSON.

## Python control plane

Python remains dependency-free at runtime. New provider and worker integrations MUST preserve the existing restrictive permission model, persistent state, and resumability. Optional workers are subprocesses first; native extensions require measured evidence that subprocess overhead is material.

## SQL memory

`SqliteMemoryStore` applies ordered, checksummed migrations. Migration checksum drift is an error. The first schema provides licensed source/document/chunk records, FTS5 synchronization, evidence-backed graph edges, retrieval traces, and hardware samples.

SQLite does not replace the manifest. Deleting the derived database must not lose authoritative project intent or provenance.

## TypeScript presentation

`web/` contains strict contracts only. A framework will be selected when an actual dashboard is implemented. This prevents premature React/Vite or server dependencies while allowing any framework to consume a stable API. Browser code MUST call the Python control plane and MUST NOT duplicate pipeline, approval, license, or validation policy.

## Rust workers

`gamedev-worker` demonstrates a bounded JSONL worker and checked resource-estimation kernel. Rust is appropriate only when profiling shows a meaningful CPU, memory, or latency bottleneck. Workers MUST:

- accept and return versioned envelopes
- avoid direct authoritative-state mutation
- reject overflow and malformed input
- expose capabilities before assignment
- enforce output and runtime limits in the Python caller
- remain optional for correctness

## Adoption gates

A new language component requires all of the following:

1. A concrete ecosystem or measured performance advantage.
2. A stable JSON/SQL contract and cross-language fixture.
3. Independent format, lint, unit, and integration tests.
4. A packaging story that does not require end users to install its toolchain.
5. No duplicate business rules across languages.
6. Measured quality, runtime, memory, or cost improvement.

## Validation

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
npm --prefix web ci
npm --prefix web test
cargo fmt --all --check
cargo clippy --workspace --all-targets -- -D warnings
cargo test --workspace
```
