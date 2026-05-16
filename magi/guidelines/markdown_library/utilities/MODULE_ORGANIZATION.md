# Module Organization

### Backend Testing Modules

The `.backend/` directory contains language-specific testing and quality tooling organized by runtime:

- **C# Module** (`.backend/csharp/`) — .NET testing infrastructure: unit test execution, code coverage analysis, integration testing against Azure resources, performance benchmarking, static analysis via Qodana. Includes Python helper modules in `codeTestSuite_modules/` that parse TRX files, coverage reports, and produce HTML dashboards.
- **Python Module** (`.backend/python/`) — Project maintenance tools: `__init__.py` regeneration, static method detection and fixing, dependency checking, file discovery utilities.
- **Rust Module** (`.backend/rust/`) — Cargo-based tooling: build verification, test execution, clippy analysis, formatting checks, security audits, benchmarking. Each tool integrates with centralized logging and produces machine-readable output.

### Common Helper Module Inventory

| Module | Purpose | Dependencies |
|:-------|:--------|:-------------|
| `colors.sh` | ANSI color codes for terminal output | None |
| `utils.sh` | Core utilities (`die`, `warn`, `have_cmd`, `is_true`) | `colors.sh` |
| `paths.sh` | Path resolution (project root, utilities root, script dir) | None |
| `env_loader.sh` | Environment file parsing and variable loading | `colors.sh`, `utils.sh` |
| `log_helper.sh` | Structured logging to centralized log directory | `colors.sh`, `utils.sh`, `paths.sh` |
| `docker_helpers.sh` | Docker operations (build, run, health checks) | `colors.sh`, `utils.sh` |
| `azure_helpers.sh` | Azure CLI wrappers and resource verification | `colors.sh`, `utils.sh` |
| `http_helpers.sh` | HTTP request utilities with timing | `utils.sh` |
| `ssh_helpers.sh` | SSH operations with sshpass integration | `colors.sh`, `utils.sh` |
| `test_helpers.sh` | Test execution utilities and result parsing | `colors.sh`, `utils.sh` |
| `dotnet_env.sh` | .NET SDK detection and configuration | `colors.sh`, `utils.sh` |
| `python_env.sh` | Python environment and venv management | `colors.sh`, `utils.sh`, `paths.sh` |
| `rust_env.sh` | Rust toolchain detection and cargo utilities | `colors.sh`, `utils.sh` |

### Module Sourcing Protocol

Scripts source modules using a validation-first pattern that fails fast on missing dependencies:

```bash
[[ -f "${COMMON_DIR}/colors.sh" ]] || { echo "ERROR: Missing colors.sh"; exit 1; }
source "${COMMON_DIR}/colors.sh"

[[ -f "${COMMON_DIR}/utils.sh" ]] || { echo -e "${RED}ERROR:${NC} Missing utils.sh"; exit 1; }
source "${COMMON_DIR}/utils.sh"
```

The first source (typically `colors.sh`) cannot use color codes in its error message because colors are not yet defined. Subsequent sources use the established color variables. **This ordering is intentional and must be preserved.**

---
[Back to Overview](./OVERVIEW.md)
