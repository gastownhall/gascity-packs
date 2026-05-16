# Bash Best Practices

### Subshell Awareness
Pipelines, command substitutions (`$(...)`), and parenthesized groups (`(...)`) execute in subshells. Variable assignments and state changes inside subshells do NOT propagate to the parent shell.
```bash
# Correct — process substitution avoids subshell
count=0
while read -r line; do
    count=$((count + 1))
done < <(some_command)
```

### Array Safety
Use arrays for lists of items. Never store multi-value data in a single string variable separated by spaces.
```bash
# Correct
files=("file one.txt" "file two.txt")
for f in "${files[@]}"; do
    process "${f}"
done
```

### Quoting Discipline
Every variable expansion and command substitution must be double-quoted unless unquoted behavior is explicitly required.
Forbidden:
- Unquoted `$variable` outside `[[ ]]`.
- Unquoted `$(command)` outside `[[ ]]`.

### Prefer Built-in String Operations
Use bash parameter expansion for simple string operations instead of spawning external processes (sed, awk).
```bash
# Remove extension
base="${filename%.*}"
# Default value
val="${input:-default}"
```

### Arithmetic Expressions
Use `(( ))` for arithmetic, `$(( ))` for expansion. Never use `expr` or `let`.
```bash
result=$((a + b * 2))
```

### Never Use ++ or -- Operators
Arithmetic commands return exit status 1 when the result is 0. Under `set -e`, `((count++))` can fail when count is 0.
```bash
# Correct
count=$((count + 1))
```

### Read Command Best Practices
When reading line by line, always use `IFS=` and `-r` to preserve whitespace and backslashes.
```bash
while IFS= read -r line || [[ -n "${line}" ]]; do
    process "${line}"
done < "${input_file}"
```

### Locale and Sort Determinism
Set `LC_ALL=C` or `LC_COLLATE=C` explicitly when deterministic output ordering matters.

---
[Back to Overview](./OVERVIEW.md)
