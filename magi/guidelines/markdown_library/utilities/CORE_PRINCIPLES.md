# Core Principles

The `.utilities` suite is a self-contained, portable automation framework designed for enterprise development workflows. It provides standardized tooling for testing, deployment, error analysis, and local development across multiple language ecosystems. These guidelines govern the architecture, usage patterns, and extension of the suite.

### Primary Design Goals

- **Absolute Portability** — The suite functions identically across any project without modification; no project-specific values exist within `.utilities/`.
- **Self-Healing Dependencies** — Missing tools trigger automatic installation via platform-appropriate package managers; scripts never fail due to absent prerequisites without attempting remediation.
- **Centralized Logging** — All operations produce structured logs in `.utilities/_logs/` for debugging, auditing, integration with external monitoring systems.
- **Modular Composition** — Each script sources only required helpers from `.common/`; no monolithic imports or circular dependencies.
- **Environment-Driven Configuration** — Runtime behavior derives from `.env` files and environment variables; hardcoded values are prohibited.

### Architectural Invariants

- **No Project-Specific References** — Scripts within `.utilities/` never reference filenames, paths, or identifiers specific to any consuming project. Configuration comes from environment variables or `.env` files in the project root, external to the utilities directory.
- **Backward Compatibility** — Modifications must not break existing integrations. New features use optional parameters with sensible defaults. Removal of functionality requires deprecation warnings across multiple releases.
- **Deterministic Outputs** — Given identical inputs and environment state, scripts produce identical results. No reliance on network state, random values, or temporal conditions beyond explicit timestamps.
- **Fail-Safe Defaults** — When configuration is ambiguous or missing, scripts default to safe, non-destructive behavior. Destructive operations require explicit confirmation or environment flags.

### Directory Contract

| Path | Purpose | Stability |
|:-----|:--------|:----------|
| `.utilities/.common/` | Shared helper modules | Stable |
| `.utilities/.backend/` | Language-specific tooling | Stable |
| `.utilities/.docker/` | Container operations | Stable |
| `.utilities/.errors/` | Error aggregation and analysis | Stable |
| `.utilities/.frontend/` | Frontend evaluation tools | Stable |
| `.utilities/.local_azure/` | Local Azure service configuration | Stable |
| `.utilities/.tools/` | External tool integrations | Experimental |
| `.utilities/_logs/` | Centralized log output | Generated |

The `.utilities/` directory structure represents a **stable API**. Consuming projects depend on specific paths remaining consistent.

---
[Back to Overview](./OVERVIEW.md)
