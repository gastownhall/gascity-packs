# Prohibited Practices

### Never Do

- Store project-specific names, paths, or identifiers in `.utilities/` scripts.
- Hardcode credentials, API keys, or connection strings.
- Skip dependency existence checks before sourcing modules.
- Use `exit` without providing meaningful error context via `die`.
- Create files outside `.utilities/` or designated output directories.
- Modify existing configuration files in the project root.
- Remove or rename existing functions without deprecation.
- Add dependencies on non-standard tools without auto-installation.
- Use bashisms that don't work in strict mode (`set -Eeuo pipefail`).
- Ignore return codes from external commands.
- Leave debugging output enabled in committed code.
- Use `echo` without `-e` for colorized output.
- Reference `$PWD` for path resolution (use `BASH_SOURCE`).
- Assume network connectivity without validation.
- Store sensitive data in log files.
- Use synchronous sleeps without progress indication.
- Skip the §19 shakedown after triggering changes to a state-mutating utility.
- Commit a `--shakedown` mode that calls mocked external commands instead of the real ones.
- Write shakedown artifacts to `/tmp`, `/var/folders`, `$TMPDIR`, `~/.cache`, or any path outside the utility's own directory.

---
[Back to Overview](./OVERVIEW.md)
