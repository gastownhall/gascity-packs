# Control Flow and Guard Patterns

### Required Fail-Fast Guard
```bash
[[ condition ]] || { printf '%s\n' "ERROR: message" >&2; exit 1; }
```

### Required Early-Return Guard
```bash
[[ condition ]] && { printf '%s\n' "value"; return 0; }
```

### Forbidden Ambiguous Chains
- `A && B || C` (multi-command chain) — B failure triggers C even when A succeeded.
- `A && B || C && D` — Unpredictable precedence.
- Any ungrouped `&&`/`||` chains simulating if-then-else.

**Exception:** Compact one-liner dispatch (e.g., `run_privileged() { [[ $EUID -eq 0 ]] && "$@" || sudo "$@"; }`) is permitted where the `&&` branch is a direct command dispatch.

### Mandatory Grouping
```bash
# Correct
{ has_glob "*.sln" || has_glob "*.csproj"; } && { printf '%s\n' "${current}"; return 0; }
# Wrong
has_glob "*.sln" || has_glob "*.csproj" && { printf '%s\n' "${current}"; return 0; }
```

### Command Substitution Guards
```bash
# Correct
path="$(compute_path)" || return 1
use_path "${path}"
# Forbidden — masks failure
use_path "$(compute_path)"
```

### Control Flow Style
#### Compact One-Liner Functions
Short functions with simple branching logic should be compact one-liners using `&&` and `||`.
```bash
run_privileged() { [[ $EUID -eq 0 ]] && "$@" || sudo "$@"; }
```

#### When to Use if/elif vs case
- **if/elif/else** — for evaluating boolean conditions (file existence, numeric comparisons).
- **case** — for matching a single value against multiple patterns.

Never force filesystem condition checks into a `case` statement.

#### Guard Clause Style
For functions that detect state and return early, prefer compact guard-clause style with `&& { ...; return; }` over nested `if/elif/else`.
```bash
resolve_editor() {
    [[ -n "${EDITOR:-}" ]] && { printf '%s\n' "${EDITOR}"; return 0; }
    command -v nvim >/dev/null 2>&1 && { printf '%s\n' "nvim"; return 0; }
    return 0
}
```

---
[Back to Overview](./OVERVIEW.md)
