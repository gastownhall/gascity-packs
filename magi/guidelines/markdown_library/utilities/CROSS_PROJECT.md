# Cross-Project Compatibility

### Project Detection

The suite detects project type for adaptive behavior:

```bash
detect_project_type() {
    local project_root="$1"
    if [[ -f "${project_root}/package.json" ]]; then
        echo "node"
    elif [[ -f "${project_root}/Cargo.toml" ]]; then
        echo "rust"
    elif [[ -f "${project_root}/pyproject.toml" ]] || [[ -f "${project_root}/setup.py" ]]; then
        echo "python"
    elif find "${project_root}" -name "*.csproj" -o -name "*.sln" | head -1 >/dev/null 2>&1; then
        echo "dotnet"
    else
        echo "unknown"
    fi
}
```

### Project-Agnostic Constraints

- **All project-specific values from environment** — never hardcoded.
- **Use path resolution functions** — never hardcoded paths.
- **Provide sensible fallbacks** for all configuration.

### Version Detection Patterns

```bash
detect_python_version() {
    local python_cmd="${1:-python3}"
    if have_cmd "${python_cmd}"; then
        local version=$("${python_cmd}" --version 2>&1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+')
        echo "${version}"
    fi
}

detect_venv() {
    if [[ -n "${VIRTUAL_ENV:-}" ]]; then
        echo "Active: ${VIRTUAL_ENV}"
    elif [[ -d "venv" ]]; then
        echo "Available: ./venv"
    elif [[ -d ".venv" ]]; then
        echo "Available: ./.venv"
    else
        echo "None"
    fi
}

detect_dotnet_version() {
    if have_cmd dotnet; then
        dotnet --list-sdks | head -1 | awk '{print $1}'
    fi
}

detect_node_version() {
    have_cmd node && node --version | sed 's/v//'
}
```

---
[Back to Overview](./OVERVIEW.md)
