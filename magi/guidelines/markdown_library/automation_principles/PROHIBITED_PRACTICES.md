# Prohibited Practices

### Never Do

- **Require README prerequisites** — If it must be done before the script runs, put it in the script
- **Use hardcoded credentials** — Credentials come from environment, files, or secret managers — never source code
- **Swallow errors silently** — Every error must be logged, handled, or propagated — never ignored
- **Assume tool availability** — Verify and install dependencies; never assume tools exist
- **Use bare `rm -rf` on variables** — `rm -rf "/${VAR}"` with empty `VAR` deletes root; validate paths before deletion
- **Disable SSL verification universally** — Disable only for specific, documented, controlled endpoints
- **Run as root unnecessarily** — Request elevation only for operations requiring it; drop privileges immediately after
- **Leave temporary files on failure** — Register cleanup in trap handlers; clean up on all exit paths
- **Use `sleep` for synchronization** — Poll for conditions; sleeping for fixed durations creates race conditions and wastes time
- **Ignore exit codes** — Check return values; nonzero exits indicate failures requiring response
- **Modify files in place without backup** — Create backups before modification; enable recovery from mistakes
- **Use relative paths for critical operations** — Convert to absolute paths early; working directory may change
- **Log sensitive values** — Mask credentials, tokens, keys, and PII in all log output
- **Retry infinitely** — Set maximum retry counts and total timeout; infinite retries become infinite hangs
- **Write platform-specific code without detection** — Detect platform and adapt; never assume Linux or macOS
- **Skip shakedown** after any change touching an integration boundary
- **Run shakedown** against mocked services, in-memory databases, or non-representative environments
- **Optimize during shakedown** — note, log, defer

### Always Do

- **Verify dependencies before use** — Check existence and version; install if missing
- **Create directories before writing files** — `mkdir -p` prevents "directory not found" errors
- **Set explicit permissions** — Specify permissions during creation; never rely on umask
- **Use absolute paths** — Resolve paths early; prevent working directory surprises
- **Validate configuration** — Type-check, range-check, and existence-check all configuration values
- **Log operation start and completion** — Provide visibility into automation progress and duration
- **Include correlation IDs in logs** — Enable tracing across distributed components
- **Clean up temporary resources** — Register cleanup handlers; execute on all exit paths
- **Return meaningful exit codes** — Communicate success/failure to calling processes
- **Document all dependencies** — List required tools, services, and configuration in automation headers
- **Test on fresh systems** — Verify self-healing by running on systems without prerequisites
- **Implement timeouts for all waits** — Network operations, process starts, lock acquisition — all need timeouts
- **Use atomic file operations** — Write to temporary file, then rename; prevent partial file corruption
- **Handle signals gracefully** — Register handlers for SIGTERM/SIGINT; clean up on termination
- **Support configuration override** — Allow environment variables to override defaults for deployment flexibility
- **Run shakedown** after every trigger condition in §21
- **Capture shakedown artifacts** — without them the shakedown did not happen

---
[Back to Overview](./OVERVIEW.md)
