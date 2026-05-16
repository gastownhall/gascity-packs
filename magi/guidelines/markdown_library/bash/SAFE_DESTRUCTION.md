# Safe Destruction & Backup

### Safe rm Patterns
Never use bare `rm -rf` on unvalidated variables. Always verify the variable is set, non-empty, and does not resolve to a dangerous path before passing it to `rm -rf`:
```bash
# Correct
[[ -n "${TMP_DIR:-}" && "${TMP_DIR}" == /tmp/* ]] && rm -rf "${TMP_DIR}"
# Wrong — catastrophic if empty or unset
rm -rf "${INSTALL_DIR}"
```

Forbidden absolutely:
- `rm -rf ${var}` without validation
- `rm -rf /` (with or without `--no-preserve-root`)

### Backup Before Modify
Before modifying or overwriting an existing file, create a timestamped backup:
```bash
backup_file() {
    local target="$1" backup
    [[ -f "${target}" ]] || return 0
    backup="${target}.backup.$(date +%s)"
    cp -p "${target}" "${backup}"
    printf '%b\n' "${FG_C}Backup: ${backup}${RST}"
}
```

### Destructive Action Confirmation
Operations that delete data, overwrite files, or make irreversible system changes must either require an explicit `--force`/`--yes` flag, or prompt for interactive confirmation. Non-interactive scripts (CI, cron) must accept a flag — never prompt on stdin in headless environments.

---
[Back to Overview](./OVERVIEW.md)
