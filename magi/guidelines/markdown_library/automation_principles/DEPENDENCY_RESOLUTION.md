# Dependency Resolution

Dependencies are the primary source of automation failures. A dependency is any resource, tool, service, or condition that must exist for automation to succeed. Self-healing automation manages dependencies proactively.

### Dependency Categories

- **Runtime tools** — Binaries and interpreters required for execution: bash, python, jq, curl, docker, kubectl.
- **Libraries and packages** — Language-specific dependencies: pip packages, npm modules, system libraries.
- **Services** — Running processes that provide capabilities: databases, message queues, container runtimes, web servers.
- **Configuration** — Files and environment variables that parameterize behavior: credentials, endpoints, feature flags.
- **Infrastructure** — Network connectivity, storage volumes, compute resources, cloud services.

### Detection Patterns

```bash
# Tool presence
command -v docker >/dev/null 2>&1

# Service availability
curl -sf http://localhost:8080/health >/dev/null 2>&1

# File existence
[[ -f /etc/myapp/config.yaml ]]

# Environment variable
[[ -n "${DATABASE_URL:-}" ]]
```

### Tool Detection and Install

```bash
ensure_tool() {
    local tool="$1"
    local package="${2:-$tool}"
    if command -v "${tool}" >/dev/null 2>&1; then
        return 0
    fi
    echo "Installing ${tool}..."
    if command -v apt-get >/dev/null 2>&1; then
        sudo apt-get update && sudo apt-get install -y "${package}"
    elif command -v dnf >/dev/null 2>&1; then
        sudo dnf install -y "${package}"
    elif command -v brew >/dev/null 2>&1; then
        brew install "${package}"
    else
        echo "Unable to install ${tool} - no supported package manager found"
        return 1
    fi
    command -v "${tool}" >/dev/null 2>&1
}
```

### Installation Strategies

- **Package manager cascade** — Try the native manager first (apt, dnf, pacman), then universal managers (snap, flatpak), then language-specific (pip, npm), then direct downloads.
- **Version management** — When multiple versions may exist, prefer version managers (pyenv, nvm, rbenv) that isolate installations and allow switching. Direct system installation of language runtimes creates version conflicts across projects.
- **Containerized dependencies** — For complex dependencies with significant configuration, prefer containerized versions. A PostgreSQL container starts faster and more reliably than installing PostgreSQL from packages.
- **Build from source** — Last resort. Requires build toolchains, takes time, introduces platform-specific complexity. Use only when no binary distribution exists.

### Installation Verification

Installation success is not assumed. After every installation attempt:

- Re-run the detection check
- Verify the installed version meets requirements
- Confirm the installation did not break existing functionality
- Test basic operations to ensure the tool is functional

### Dependency Documentation

Every script must document its dependencies explicitly:

- Required tools with minimum versions
- Required services with connectivity parameters
- Required configuration with acceptable value ranges
- Optional enhancements with degraded behavior description

---
[Back to Overview](./OVERVIEW.md)
