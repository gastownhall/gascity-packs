# Functions

### Declaration Rules
- `snake_case` naming (no camelCase, PascalCase, or kebab-case).
- Declared before use.
- `local` for all temporaries.
- Explicit `return` on all paths.
- POSIX `name()` form — never the Bash-only `function name {}` syntax.

```bash
process_file() {
    local file="$1" content
    [[ -f "${file}" ]] || return 1
    content="$(cat "${file}")" || return 1
    printf '%s\n' "${content}"
    return 0
}
```

### Entry Point
```bash
main() {
    parse_args "$@"
    preflight
    run
}
main "$@"
```

### Function Documentation
Non-trivial functions should include a brief comment block describing purpose, arguments, return values, and side effects:
```bash
# Validate that a given path is a writable directory.
# Arguments: $1 - directory path to validate
# Returns: 0 on success, 1 if path is invalid or not writable
validate_output_dir() {
    local dir_path="$1"
    [[ -d "${dir_path}" ]] || return 1
    [[ -w "${dir_path}" ]] || return 1
    return 0
}
```

### Function Length Limit
Functions should not exceed approximately 50 lines. If a function grows beyond this, decompose it into smaller, single-purpose helpers. Long functions are harder to test, debug, and reason about.

---
[Back to Overview](./OVERVIEW.md)
