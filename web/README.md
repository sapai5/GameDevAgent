# GameDevAgent web boundary

This package provides strict TypeScript contracts for a future local web console. It deliberately does not select React, Vue, Svelte, or another framework yet. A UI framework belongs above these contracts after the telemetry or knowledge-graph dashboard has a concrete product requirement.

The web boundary is presentation-only. It MUST NOT duplicate pipeline, approval, license, or validation policy owned by the Python control plane.

```bash
npm ci
npm test
```
