# Security Considerations

### Input Validation
Never trust external input (arguments, env vars, file contents):
```bash
[[ "${input}" =~ ^[a-zA-Z0-9_-]+$ ]] || { printf 'ERROR: Invalid input\n' >&2; exit 1; }
```

### Credential Handling
- Never log credentials.
- Never store in script files.
- Use environment variables or credential managers.
- Clear sensitive variables after use: `unset PASSWORD`.

### Temporary Files
- Use `mktemp` with restrictive permissions.
- Clean up unconditionally via trap.

### Command Injection Prevention
- Always quote variables.
- Use `--` to terminate option parsing.
- Use arrays for command building:
```bash
cmd=("prog" "--opt" "${val}")
"${cmd[@]}"
```

### Restrictive Umask
Set a restrictive umask at the start of scripts:
```bash
umask 077  # Owner-only by default for new files/dirs
```

### No SSL Verification Bypass
Never disable SSL/TLS certificate verification (`curl --insecure`) in production.

---
[Back to Overview](./OVERVIEW.md)
