# Troubleshooting Guide

### "Command not found" after installation
The install modified PATH but current shell doesn't have it. Solutions:
- Source the profile: `source ~/.bashrc`.
- Use absolute path: `/usr/local/bin/cmd`.
- Verify installation actually succeeded.

### Script works interactively, fails in cron
Cron has minimal environment. Fixes:
- Set PATH explicitly at script top.
- Use absolute paths for all commands.
- Redirect output to log file.

### "Unbound variable" errors
`set -u` caught an unset variable. Fixes:
- Use defaults: `${VAR:-default}`.
- Check before use: `[[ -n "${VAR:-}" ]]`.

### last line dropped from `while IFS= read -r line` loop
Loop drops the final line if it lacks a trailing newline. Fix:
```bash
while IFS= read -r line || [[ -n "${line}" ]]; do
    process "${line}"
done < "${input_file}"
```

### Increment with `((var++))` randomly aborts under `set -e`
Pre-increment of 0 returns exit status 1. Fix: use `var=$((var + 1))` instead.

### Error in function doesn't exit script
`set -e` is suppressed inside `if`, `&&`, `||`. Fix:
- Explicit `|| return 1` in functions.
- Check return value: `func || exit 1`.

---
[Back to Overview](./OVERVIEW.md)
