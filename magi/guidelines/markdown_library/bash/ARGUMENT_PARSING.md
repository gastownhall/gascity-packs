# Argument Parsing

### Shift-Based Parsing
```bash
parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            -v|--verbose) VERBOSE=1; shift ;;
            -f|--file) FILE="$2"; shift 2 ;;
            -h|--help) usage; exit 0 ;;
            --) shift; break ;;
            -*) printf '%b\n' "${FG_R}ERROR: Unknown option: $1${RST}" >&2; exit 2 ;;
            *) ARGS+=("$1"); shift ;;
        esac
    done
}
```

### Required Argument Validation
```bash
validate_args() {
    [[ -n "${FILE:-}" ]] || { printf '%b\n' "${FG_R}ERROR: --file required${RST}" >&2; exit 2; }
    [[ -f "${FILE}" ]] || { printf '%b\n' "${FG_R}ERROR: File not found: ${FILE}${RST}" >&2; exit 2; }
}
```

### Help Flag Required
Every script that accepts arguments must support `-h` and `--help`. The help output should match the USAGE section in the header block.

---
[Back to Overview](./OVERVIEW.md)
