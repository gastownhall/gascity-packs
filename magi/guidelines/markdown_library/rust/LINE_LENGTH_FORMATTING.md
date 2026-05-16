# Line Length and Formatting

### Maximum Line Length
- **Hard limit**: 220 characters per line
- **Philosophy**: Use horizontal space efficiently before breaking lines

### Formatting Priority
1. **Single-line preference** for:
    - Function signatures (including parameters, generics, return types)
    - Everything between parentheses `(` and `)`
    - Simple expressions and statements
    - Import statements
2. **Multi-line formatting** when:
    - Exceeding 220 characters
    - Complex nested structures (3+ levels deep)
    - Multiple statements required

### Trailing Commas
- **Required** in multi-line structures:
    - Function parameter lists
    - Struct field lists
    - Match arms
    - Import groups
    - Enum variants
- **Optional** in single-line structures

### Rustfmt Configuration Override
Place in `rustfmt.toml` at project root:
```toml
max_width = 220
use_small_heuristics = "Max"
fn_params_layout = "Compressed"
struct_lit_single_line = true
where_single_line = true
imports_granularity = "Crate"
group_imports = "StdExternalCrate"
```

---
[Back to Overview](./OVERVIEW.md)
