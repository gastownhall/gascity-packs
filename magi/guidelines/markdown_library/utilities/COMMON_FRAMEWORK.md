# Common Module Framework

### Utility Functions (`utils.sh`)

| Function | Purpose |
|:---------|:--------|
| `die` | Terminates execution with formatted error message. All unrecoverable errors use `die` rather than direct `exit` |
| `warn` | Outputs warning message without terminating |
| `info` | Outputs informational message |
| `have_cmd` | Checks if a command exists in PATH (returns 0 if found). Prefer over `command -v` for consistency |
| `is_true` | Evaluates boolean-like values (`1`, `true`, `yes`, `y`) |
| `detect_os` | Returns normalized OS identifier (`darwin`, `linux`) |
| `detect_linux_distro` | Returns distribution identifier for package manager selection |

### Path Resolution (`paths.sh`)

| Function | Purpose |
|:---------|:--------|
| `resolve_script_dir` | Returns absolute path of the directory containing the calling script (uses `BASH_SOURCE`) |
| `resolve_project_root` | Traverses upward searching for project markers (`.git/config`, `.env`, `pyproject.toml`, `package.json`) |
| `resolve_utilities_root` | Traverses upward searching for the `.utilities` directory structure |
| `get_central_log_dir` | Returns path to `.utilities/_logs/`, creating it if necessary |
| `normalize_path_no_deref` | Normalizes a path **without dereferencing symlinks** — critical for symlinked tool installations |

### Environment Loading (`env_loader.sh`)

| Function | Purpose |
|:---------|:--------|
| `load_env_file` | Reads `.env` file and exports all defined variables. Handles comments, empty lines, quoted values. **Does not override existing environment variables unless explicitly requested** |
| `read_env_value` | Extracts a single value from an `.env` file without loading all variables |
| `require_env_var` | Validates required environment variable is set, terminating with `die` if missing |

```bash
PROJECT_NAME=my-application
ENVIRONMENT=development
DATABASE_HOST="localhost"  # Local development
```

---
[Back to Overview](./OVERVIEW.md)
