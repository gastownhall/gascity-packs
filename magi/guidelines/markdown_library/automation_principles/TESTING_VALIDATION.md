# Testing and Validation

Self-healing automation must be testable. Testing validates that automation works correctly and that self-healing mechanisms function as designed.

### Test Categories

- **Unit tests** — Test individual functions in isolation. Mock external dependencies. Fast execution.
- **Integration tests** — Test interactions between components. Use real dependencies where practical.
- **End-to-end tests** — Execute complete automation in realistic environments. Verify intended outcomes.

### Environment Isolation

- Use dedicated test environments
- Clean up all created resources after tests
- **Never run destructive tests against production infrastructure**
- Isolate test network traffic from production

### Fresh System Testing

Self-healing claims require fresh-system validation:

```bash
docker run -it --rm ubuntu:24.04
docker cp script.sh container:/script.sh
docker exec container /script.sh
# Verify success
```

If automation requires manual intervention on a fresh system, **it is not self-healing.**

### Failure Injection

Test self-healing by injecting failures:
- Remove dependencies before execution
- Corrupt configuration files
- Simulate network failures
- Fill disk to test space handling
- Kill processes during execution

### Validation Assertions

After automation completes, validate outcomes:
- Services are running and healthy
- Configuration files contain expected values
- Network endpoints respond correctly
- Permissions are set appropriately
- No error messages in logs

---
[Back to Overview](./OVERVIEW.md)
