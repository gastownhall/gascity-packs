# Environment and Configuration

### Configuration Hierarchy

| Layer | Source | Override priority |
|:-----:|:-------|:------------------|
| 1 | Built-in defaults (hardcoded fallback values) | Lowest |
| 2 | Suite configuration (`.utilities/.common/`) | |
| 3 | Project configuration (`${PROJECT_ROOT}/.env`) | |
| 4 | Environment overrides (shell environment) | |
| 5 | Command-line arguments | Highest |

Later layers override earlier ones.

### Required Environment Variables

| Module | Required vars |
|:-------|:--------------|
| Docker Operations | `IMAGE_NAME`, `CONTAINER_NAME`; optional: `DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_PASS` |
| C# Testing | `PROJECT_NAME`, `TEST_PROJECT`, `DOTNET_ROOT` (auto-detected if unset) |
| Azure Integration | `SUBSCRIPTION_ID`, `RESOURCE_GROUP_PATTERN`, `TEST_TENANT`, `TEST_CLIENT` |
| Local Azure Services | Service-specific connection strings and ports defined in `local-azure-services.json` |

### Configuration File Formats

| Format | Use |
|:-------|:----|
| `.env` | Key-value pairs for simple configuration. Loaded into shell environment. Credentials, feature flags, simple strings |
| `.json` | Structured configuration for complex service definitions. Parsed by language-specific loaders (C#, Python, Rust) |

---
[Back to Overview](./OVERVIEW.md)
