# /check-project - Comprehensive Project Validation Using .utilities/

## INITIATING COMPREHENSIVE PROJECT VALIDATION

This command performs intelligent project validation using the `.utilities/` framework, detecting project type and running all applicable checks.

## EXECUTION PROTOCOL

### Phase 1: Environment Detection
Detect and catalog all project components:
```bash
# Check for backend languages
[[ -f "requirements.txt" || -f "pyproject.toml" || -d "venv" || -d ".venv" ]] && BACKEND_PYTHON=true
[[ -f "*.csproj" || -f "*.sln" || -f "Program.cs" ]] && BACKEND_CSHARP=true
[[ -f "Cargo.toml" || -f "Cargo.lock" ]] && BACKEND_RUST=true

# Check for frontend
[[ -f "package.json" || -d "src/components" || -d "frontend" ]] && FRONTEND=true

# Check for Docker
[[ -f "Dockerfile" || -f "docker-compose.yml" ]] && DOCKER=true

# Check for database
[[ -f "*.sql" || -d "migrations" || -f "schema.prisma" ]] && DATABASE=true
```

### Phase 2: Backend Validation

#### Python Backend
If Python is detected, execute:
```bash
# Pre-check and environment setup
.utilities/.backend/python/_preCheck.sh

# Rebuild __init__ files if needed
.utilities/.backend/python/_rebuild_init_files.sh

# Run Python-specific validations
source .utilities/.common/python_env.sh
activate_python_venv
python -m pytest --tb=short --maxfail=5
python -m mypy . --strict --no-error-summary
python -m ruff check .
python -m black --check .
deactivate || true
```

#### C# Backend
If C# is detected, execute:
```bash
# Run comprehensive C# test suite
.utilities/.backend/csharp/_codeTestSuite.sh

# Health check
.utilities/.backend/csharp/_healthCheck.sh

# Integration tests
.utilities/.backend/csharp/_integrationTestSuite.sh

# Performance tests if requested
.utilities/.backend/csharp/_performanceTestSuite.sh

# Generate Qodana configuration
.utilities/.backend/csharp/_generateQodanaConfig.sh
```

#### Rust Backend
If Rust is detected, execute:
```bash
# Build and test
.utilities/.backend/rust/_cargoBuildTest.sh

# Clippy linting
.utilities/.backend/rust/_cargoClippy.sh

# Format check
.utilities/.backend/rust/_cargoFormat.sh

# Security audit
.utilities/.backend/rust/_cargoAudit.sh

# Run test suite
.utilities/.backend/rust/_rustTestSuite.sh

# Benchmarks if requested
.utilities/.backend/rust/_cargoBench.sh
```

### Phase 3: Frontend Validation

If frontend is detected, execute:
```bash
# Comprehensive frontend validation
.utilities/.frontend/validate_frontend.sh

# Route discovery for deployed environment
python .utilities/.frontend/discover_routes.py --env deployed

# Generate Playwright tests
python .utilities/.frontend/generate_playwright_spec.py

# Run Playwright tests if available
if command -v playwright &> /dev/null; then
    playwright test
fi

# Screenshot analysis for visual regression
.utilities/.frontend/deployed/screenshot_analyzer.sh || true
```

### Phase 4: Docker Validation

If Docker is detected, execute:
```bash
# Build Docker images
.utilities/.docker/build.sh

# Run container health checks
.utilities/.docker/start.sh --health-check

# Validate container logs
.utilities/.docker/container_logs.sh --validate

# Test local deployment
.utilities/.docker/run_local.sh --test

# Clean up test containers
.utilities/.docker/stop.sh --cleanup
```

### Phase 5: Database Validation

If database is detected, execute appropriate checks:
```bash
# MongoDB checks
[[ -f "*.mongodb" || -d "mongodb" ]] && .utilities/.database/mongodb/validate.sh

# SQL database checks
[[ -f "*.sql" ]] && .utilities/.database/sql/validate.sh

# SQLite checks
[[ -f "*.db" || -f "*.sqlite" ]] && .utilities/.database/sqlite/validate.sh

# CosmosDB checks
[[ -f "cosmos.config" ]] && .utilities/.database/cosmosdb/validate.sh
```

### Phase 6: Error Analysis

Run comprehensive error checking:
```bash
# Collect all errors from logs
.utilities/.errors/getErrors.sh

# Process and categorize errors
python .utilities/.errors/process_errors.py

# Combine error reports
.utilities/.errors/combine_errors.sh

# Search for critical keywords
.utilities/.errors/_find_keyword.sh "ERROR" "FAIL" "EXCEPTION" "CRITICAL"
```

### Phase 7: Code Analysis

Run static analysis tools:
```bash
# Find problematic patterns
.utilities/.analysis/search_destroy.sh

# Language-specific analysis
[[ "$BACKEND_RUST" == "true" ]] && {
    .utilities/.analysis/rust_report.sh
    .utilities/.analysis/rust_check_empty_files.sh
    .utilities/.analysis/rust_duplicate_symbols_report.sh
}

# Keyword analysis for security issues
.utilities/.analysis/find_keyword.sh "password" "secret" "token" "api_key"
```

### Phase 8: Clean-up Operations

If requested, run cleanup:
```bash
# Clean build artifacts
.utilities/.cleanup/clean_build_artifacts.sh

# Clean logs older than 7 days
.utilities/.cleanup/clean_old_logs.sh

# Clean temporary files
.utilities/.cleanup/clean_temp_files.sh
```

## VALIDATION MATRIX

| Component | Detection | Validation Scripts |
|-----------|-----------|-------------------|
| Python | `requirements.txt`, `*.py` | `_preCheck.sh`, pytest, mypy, ruff, black |
| C# | `*.csproj`, `*.sln` | `_codeTestSuite.sh`, `_healthCheck.sh`, `_integrationTestSuite.sh` |
| Rust | `Cargo.toml` | `_cargoBuildTest.sh`, `_cargoClippy.sh`, `_cargoAudit.sh` |
| Frontend | `package.json` | `validate_frontend.sh`, route discovery, Playwright |
| Docker | `Dockerfile` | `build.sh`, `run_local.sh`, container validation |
| Database | `*.sql`, `*.db` | Database-specific validation scripts |

## OUTPUT REQUIREMENTS

### Success Indicators
- All tests pass with zero failures
- Zero linting errors
- Zero security vulnerabilities
- All containers healthy
- Database connections successful
- No critical errors in logs

### Failure Handling
- Stop on first critical failure
- Log all errors to `.utilities/_logs/`
- Generate failure report with remediation steps
- Exit with non-zero status code

## EXECUTION FLAGS

```bash
# Full validation (default)
/check-project

# Quick validation (skip performance tests)
/check-project --quick

# Backend only
/check-project --backend-only

# Frontend only
/check-project --frontend-only

# Docker validation only
/check-project --docker-only

# With cleanup
/check-project --with-cleanup

# Verbose output
/check-project --verbose
```

## COMPLIANCE VERIFICATION

After running `/check-project`, verify:
1. All applicable utilities were executed
2. No manual intervention was required
3. All scripts ran to completion
4. Comprehensive report generated
5. Exit status reflects actual state

## ERROR RECOVERY

If validation fails:
1. Check `.utilities/_logs/` for detailed output
2. Review error categorization in error reports
3. Fix identified issues
4. Re-run validation
5. Confirm all checks pass

## IMPORTANT NOTES

- **NEVER** skip utilities that exist in `.utilities/`
- **ALWAYS** source common utilities before execution
- **ALWAYS** check exit codes and handle failures
- **NEVER** assume defaults - detect actual project structure
- **ALWAYS** generate comprehensive output logs

**NOW EXECUTING PROJECT VALIDATION...**