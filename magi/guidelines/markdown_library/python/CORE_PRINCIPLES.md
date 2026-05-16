# Core Principles (Non-Negotiable)

1. **Type Everything, Validate Everything** — Every function parameter and return value has type hints. Complex data uses Pydantic models. Code must pass `mypy --strict`. `Any` is forbidden in application code.
2. **Maximize Horizontal Density** — The 200-character line limit exists to be used. Single-line forms preferred when they fit. Multi-line is a last resort, except where consistency rules force multi-line across a file.
3. **No Backwards Compatibility Shims** — When refactoring, delete old code. Never wrap new implementations in legacy-named shims. If external compatibility matters, version the API properly.
4. **Single Source of Truth** — Types, enums, constants, and models defined once in `typings/` and imported everywhere. Duplicate definitions are forbidden. Never create overlapping symbol types.
5. **Deduplication as Architecture** — Shared utilities and patterns extracted aggressively. Copy-paste is technical debt.
6. **Circular Import Resolution Is Top Priority** — Eliminating circular imports is the highest priority. Correct typing is second.
7. **Validate at Boundaries Once, Trust Internally** — Convert untrusted input into typed Pydantic models at the boundary. Internal code operates on typed objects only.
8. **Optimize for Review Speed** — Names, signatures, and models carry meaning. If reviewers need narration, the design is wrong.

---
[Back to Overview](./OVERVIEW.md)
