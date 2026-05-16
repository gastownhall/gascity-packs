# Configuration Management

### Configuration Precedence
When configuration comes from multiple sources, apply this strict precedence (higher priority overrides lower):
1. Command-line arguments (highest)
2. Environment variables
3. Configuration files
4. Discovered defaults (auto-detected values)
5. Hardcoded defaults (lowest)

### Configuration Validation
Validate all configuration values after loading and before use. Check types, ranges, required fields, and enum membership. Fail fast with a clear error if validation fails — do not attempt to run with invalid configuration.

---
[Back to Overview](./OVERVIEW.md)
