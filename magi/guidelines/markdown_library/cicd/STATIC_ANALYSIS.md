# Static Analysis and Code Quality

### Linters and Formatters

Run linters and formatters on every PR. Enforce a **zero-warning policy** for new code. Use autoformatters (`prettier`, `black`, `gofmt`, `rustfmt`) to eliminate style debates.

### SAST

Run SAST (Static Application Security Testing) on every PR. Tools: Semgrep, SonarQube, CodeQL, Bandit, Gosec. Detects:
- SQL injection patterns
- XSS sinks
- Insecure cryptographic usage
- Hardcoded secrets
- Unsafe deserialization

**Block PRs with high-severity findings.**

### Type Checking

Run type checking as a CI gate for dynamically typed languages:
- `mypy` for Python
- `tsc --noEmit` for TypeScript
- PHPStan for PHP

### IaC Linting and Security Scanning

Run on IaC changes: `tflint`, `checkov`, `tfsec`, `kube-linter`. Catch open security groups, unencrypted storage, overly permissive IAM policies before they reach any environment.

---
[Back to Overview](./OVERVIEW.md)
