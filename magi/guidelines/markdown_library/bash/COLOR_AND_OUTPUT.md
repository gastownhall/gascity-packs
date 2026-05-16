# Color Definitions and Semantic Usage

### Color Variable Naming Convention
Color variables MUST use the standardized short-name convention. All declared `readonly`. When a common utilities file is in use, color definitions belong in the utilities file, not in each individual script.
```bash
# Reset
readonly RST=$'\033[0m'        # Full reset (colors + attributes)
#
# Standard foreground colors
readonly FG_K=$'\033[30m'      # Black
readonly FG_R=$'\033[31m'      # Red
readonly FG_G=$'\033[32m'      # Green
readonly FG_Y=$'\033[33m'      # Yellow
readonly FG_B=$'\033[34m'      # Blue
readonly FG_M=$'\033[35m'      # Magenta
readonly FG_C=$'\033[36m'      # Cyan
readonly FG_W=$'\033[37m'      # White
```
Prefix conventions: `FG_` foreground, `BG_` background, `BR_` bright, `BD_` bold, `UL_` underline. No helper functions for colors. No dynamic generation. Always use `$'...'` for ANSI escapes.

### Semantic Color Mapping (Mandatory)
Console colors MUST follow this semantic mapping so meaning is recognizable by color alone:

| Color | Variable | Meaning |
|-------|----------|---------|
| White | `FG_W` | General statements, neutral prose, default output |
| Blue | `FG_B` | Actions being taken (e.g., "Installing jq...") |
| Magenta | `FG_M` | Important info the user must not miss (follow-up steps, critical config) |
| Cyan | `FG_C` | Informational details, status, paths, metadata |
| Yellow | `FG_Y` | Warnings and concerning behavior |
| Red | `FG_R` | Exclusively for failures and errors |
| Green | `FG_G` | Exclusively for success confirmations |

Red MUST NOT be used for non-error output. Random or decorative color choices defeat the purpose.

### Color Reset Discipline
Every `printf` that opens a color code MUST close it with `${RST}` before the end of that printf. Unclosed color codes corrupt all subsequent output (including other processes' output) and contaminate log files if stripping fails.
```bash
# Correct
printf '%b\n' "${FG_B}Deploying...${RST}"
# Wrong — colors leak into following lines
printf '%b\n' "${FG_B}Deploying..."
```

### Output Best Practices
#### printf Only
`echo` is forbidden in any form (`echo`, `echo -e`, `echo -n`). Use `printf`:
```bash
printf '%s\n' "plain message"
printf '%b\n' "${FG_G}Success${RST}"
printf '%-30s|%-12s\n' "${name}" "${status}"
```

#### STDERR for Errors
```bash
printf '%b\n' "${FG_R}ERROR:${RST} message" >&2
```

#### Verbosity Control
```bash
VERBOSE="${VERBOSE:-0}"
readonly VERBOSE
is_verbose() { [[ "${VERBOSE}" == "1" ]]; }
vprintf() { is_verbose && printf "$@"; }
status() { printf '%b\n' "$@"; }
```

#### Conditional Output
```bash
run_command() {
    local cmd="$1"
    if is_verbose; then
        "${cmd}"
    else
        "${cmd}" >/dev/null 2>&1
    fi
}
```

---
[Back to Overview](./OVERVIEW.md)
