# Backend Testing Infrastructure

### C# Test Suite Architecture

| Script | Purpose |
|:-------|:--------|
| `_codeTestSuite.sh` | Full testing workflow: solution build, test discovery, `dotnet test` execution, coverage via Coverlet, TRX parsing, HTML report generation. Produces structured JSON summaries for CI |
| `_integrationTestSuite.sh` | Executes integration tests against deployed Azure environments. Validates AKS clusters, Application Gateways; sets environment-specific configuration |
| `_performanceTestSuite.sh` | Performance benchmarks with baseline comparison. Detects regressions and fails CI when performance degrades beyond configured thresholds |
| `_healthCheck.sh` | Validates service health endpoints with retry logic. Used in deployment pipelines to gate traffic shifting |

### Python Helper Modules

The `codeTestSuite_modules/` package:

| Module | Purpose |
|:-------|:--------|
| `trx_parser.py` | Parses Visual Studio TRX test result files |
| `coverage_parser.py` | Parses Cobertura XML coverage reports; calculates line and branch coverage |
| `metrics_collector.py` | Aggregates metrics from multiple sources into a unified `TestMetrics` model |
| `report_generator.py` | Generates HTML reports with dark-themed dashboards |

### Rust Testing Workflow

| Script | Purpose |
|:-------|:--------|
| `_rustTestSuite.sh` | Test execution with optional coverage via cargo-tarpaulin |
| `_cargoBuildTest.sh` | Build and test in a single invocation |
| `_cargoClippy.sh` | Clippy analysis with configurable strictness; supports deny-warnings mode |
| `_cargoFormat.sh` | rustfmt formatting check or apply |
| `_cargoAudit.sh` | cargo-audit against the RustSec advisory database |
| `_cargoBench.sh` | criterion benchmarks with baseline comparison |

### Python Backend Tooling

| Script | Purpose |
|:-------|:--------|
| `_rebuild_init_files.sh` | Regenerates `__init__.py` files across Python packages |
| `_static_methods.sh` | Detects methods that should be static; works with `fix_static_methods.py` |
| `_preCheck.sh` | Validates Python environment, virtual environment, required packages |
| `_find_py_files.sh` | Discovers Python files for batch processing |

---
[Back to Overview](./OVERVIEW.md)
