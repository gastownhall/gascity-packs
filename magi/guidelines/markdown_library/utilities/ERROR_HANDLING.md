# Error Handling Framework

### Error Aggregation System

| Script | Purpose |
|:-------|:--------|
| `getErrors.sh` | Scans source files for TODO, FIXME, HACK, XXX, and custom markers. Produces structured reports |
| `combine_errors.sh` | Merges error reports from multiple sources |
| `_find_keyword.sh` | Searches for specific keywords across the codebase with context extraction |
| `process_errors.py` | Categorizes, deduplicates, and generates prioritized remediation lists |

### Error Ignore Configuration

```text
# Exclude generated files
**/obj/**
**/bin/**
**/node_modules/**

# Exclude documentation TODOs
**/docs/**

# Exclude test fixtures with intentional errors
**/test_fixtures/**
```

The `.ignoreErrors` file uses gitignore-style glob patterns. Lines starting with `#` are comments.

### Error Report Formats

| Format | Use |
|:-------|:----|
| JSON | Machine-readable for CI integration; file path, line number, error type, message, surrounding context |
| Markdown | Human-readable for documentation and code review; groups errors by type and file |
| Console | Colorized output for interactive use; summary statistics and critical errors |

---
[Back to Overview](./OVERVIEW.md)
