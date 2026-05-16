# File System Operations

File system operations appear simple but contain numerous failure modes. Self-healing automation handles file operations defensively.

### Directory Operations

- **Creation** — Always use recursive creation (`mkdir -p`). Parent directories may not exist. Creation is idempotent.
- **Permissions** — Set explicit permissions during creation. Default umask varies. Restrictive defaults (0750) are safer than permissive.
- **Ownership** — Verify ownership after creation. Running as root creates root-owned directories that other users cannot access.
- **Cleanup** — Remove temporary directories in cleanup handlers. Use unique names to prevent collisions between parallel executions.

### File Operations

- **Existence checks** — Verify before read operations. Race conditions exist between check and use, but checks prevent obvious errors.
- **Atomic writes** — Write to temporary file, then rename. Rename is atomic on POSIX systems. Prevents partial file corruption during failures.
- **Backup before modify** — Copy original before modification. Enables recovery when modification fails or produces incorrect results.
- **Permission verification** — Check read/write access before operations. Failed permission checks are more informative than generic I/O errors.

### Safe File Update Pattern

```bash
safe_file_update() {
    local target="$1"
    local content="$2"
    local backup="${target}.backup.$(date +%s)"
    local temp="${target}.tmp.$$"
    [[ -f "${target}" ]] && cp "${target}" "${backup}"
    echo "${content}" > "${temp}"
    mv "${temp}" "${target}"
}
```

### Temporary Files

- **Location** — Use `/tmp` or `TMPDIR` environment variable. Never hardcode paths that may not exist or may not be writable.
- **Naming** — Use `mktemp` for unique names. Include process ID and timestamp to prevent collisions.
- **Cleanup** — Register cleanup in trap handlers. Cleanup must run regardless of exit path.
- **Security** — Set restrictive permissions (0600). Temporary files with secrets must not be world-readable.

### Path Handling

- **Absolute paths** — Convert relative paths to absolute early. Working directory may change during execution.
- **Path validation** — Verify paths do not escape intended boundaries. Prevent path traversal attacks in paths from external input.
- **Cross-platform** — Use portable path handling. Avoid assumptions about path separators or maximum path lengths.

---
[Back to Overview](./OVERVIEW.md)
