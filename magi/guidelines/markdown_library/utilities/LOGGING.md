# Logging Infrastructure

### Centralized Log Management

All suite tools produce logs in `.utilities/_logs/`:

- **Log file naming:** `{tool_name}_{timestamp}.log` (e.g., `codeTestSuite_241220_143022.log`).
- **Directory management:** `ensure_central_log_dir` creates the log directory if missing. Typically gitignored.

### Log Helper Functions

| Function | Purpose |
|:---------|:--------|
| `setup_tool_logging` | Initializes logging for a tool; creates log file, writes header metadata, returns log file path |
| `log_info`, `log_warn`, `log_error` | Write timestamped entries at appropriate severity levels |
| `log_section` | Marks section boundaries in the log for easier navigation |
| `finalize_tool_logging` | Writes footer metadata (exit code, duration) and closes the log file |
| `tee_to_log_strip_ansi` | Pipes output to both stdout and log file, stripping ANSI escape codes from the logged version |

### Log Format

```text
================================================================================
Tool: codeTestSuite
Started: 2024-12-20 14:30:22
================================================================================

[2024-12-20 14:30:22] [INFO] Loading environment from /project/.env
[2024-12-20 14:30:23] [INFO] Building solution...
[2024-12-20 14:31:15] [WARN] Coverage below threshold: 72%
[2024-12-20 14:31:20] [ERROR] Test failure in UserServiceTests.cs

================================================================================
Completed: 2024-12-20 14:31:20
Exit Code: 1
Duration: 58 seconds
================================================================================
```

---
[Back to Overview](./OVERVIEW.md)
