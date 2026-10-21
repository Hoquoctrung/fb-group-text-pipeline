# Architecture Decisions — Phase 0 + Phase 1

| Decision | Choice | Reason |
|---|---|---|
| Python | 3.11+ | SPEC requirement |
| Collector contract | `Collector.iter_posts() -> Iterator[RawPost]` | Stable adapter boundary |
| Bronze record | `RawPost` Pydantic model | Explicit contract between stages |
| Primary browser channel | Passive response observation | No manually constructed GraphQL requests |
| DOM fallback | Not implemented in the 48-hour scope if GraphQL works | §0b scope reduction |
| API / streaming demos | Theory-only; no demo code | Explicit §0b exclusion |
| Comments | Disabled | Outside minimal P0 collector scope |
| Synthetic data | Deterministic with seed 42 | Reproducible local tests |
| Checkpoint | Atomic JSON | Small and sufficient for local resume |
| Facebook schema | No schema assumed | Real key paths must be verified against anonymized probe samples |
| Authentication | Manual browser login; local storage state | Passwords are never stored by the application |
| Privacy | HMAC author hash + basic PII scrubbing | Minimize persistent identifiers |
| Storage backends | Not implemented in Phase 0 + 1 | SQLite and Parquet/DuckDB belong to later phase |
