# Required Practices

### Always Do

- Validate file existence before sourcing: `[[ -f "$FILE" ]] || { ...; exit 1; }`.
- Use `local` for all function-scoped variables.
- Use `readonly` for script-level constants.
- Provide `--help` output for user-facing scripts.
- Log all significant operations to centralized logs.
- Clean up temporary files in `EXIT` traps.
- Quote all variable expansions: `"${VAR}"`.
- Use explicit error messages with color formatting.
- Test on both macOS and Linux before committing.
- Implement auto-installation for any new dependencies.
- Document new environment variables in this guide.
- Use `die` for unrecoverable errors with context.
- Preserve existing function signatures when modifying.
- Support both interactive and non-interactive execution.
- Expose `--shakedown` mode (or companion `shakedown.sh`) on every state-mutating utility.
- Run shakedown after every triggering change before declaring the utility ready.

---
[Back to Overview](./OVERVIEW.md)
