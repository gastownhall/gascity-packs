# Filesystem Operations

### Glob Detection
```bash
has_glob() { [[ $# -eq 1 ]] && compgen -G "$1" >/dev/null; }
```

### Path Tests
```bash
[[ -d "${dir}" ]]      # Directory exists
[[ -f "${file}" ]]     # File exists
[[ -r "${file}" ]]     # Readable
[[ -w "${file}" ]]     # Writable
[[ -x "${file}" ]]     # Executable
[[ -L "${link}" ]]     # Symlink
[[ -s "${file}" ]]     # Non-empty
```

### Temporary Files
Use `mktemp` with restrictive permissions; clean up unconditionally via trap; never use predictable names:
```bash
TMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/script.XXXXXX")"
readonly TMP_DIR
trap 'rm -rf "${TMP_DIR}"' EXIT
```

### Atomic Write
```bash
write_atomic() {
    local target="$1" content="$2" tmp
    tmp="${target}.tmp.$$"
    printf '%s\n' "${content}" > "${tmp}"
    mv -f "${tmp}" "${target}"
}
```

### Create Parent Directories Before Writing
Always ensure the parent directory exists before writing a file. Self-healing pattern that prevents trivial failures:
```bash
mkdir -p "$(dirname -- "${output_file}")"
printf '%s\n' "${content}" > "${output_file}"
```

---
[Back to Overview](./OVERVIEW.md)
