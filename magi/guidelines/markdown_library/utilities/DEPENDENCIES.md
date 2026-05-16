# Dependency Management

### Auto-Installation Philosophy

The suite implements **aggressive auto-installation** of missing dependencies. Scripts never fail solely due to missing tools without first attempting installation.

### Installation Cascade

| Tier | Method |
|:----:|:-------|
| 1 | Platform-native package manager (Homebrew on macOS, apt/dnf/pacman on Linux) |
| 2 | Language-specific installers (pip, cargo, npm) |
| 3 | Version managers (pyenv, rustup, nvm) |
| 4 | Direct download from official sources |

### Tool Detection

```bash
have_cmd() {
    command -v "$1" >/dev/null 2>&1
}

check_dependencies() {
    local -a missing=()
    for cmd in "$@"; do
        have_cmd "$cmd" || missing+=("$cmd")
    done
    if [[ ${#missing[@]} -gt 0 ]]; then
        echo "Missing: ${missing[*]}"
        return 1
    fi
    return 0
}
```

### Auto-Install Pattern

```bash
ensure_dependency() {
    local tool="$1"
    local install_func="install_${tool}"
    if ! have_cmd "${tool}"; then
        info "Installing ${tool}..."
        if declare -f "${install_func}" >/dev/null; then
            "${install_func}" || die "Failed to install ${tool}"
        else
            auto_install_tool "${tool}" || die "Failed to install ${tool}"
        fi
    fi
}

auto_install_tool() {
    local tool="$1"
    if [[ "${OS}" == "Darwin" ]]; then
        ensure_homebrew && brew install "${tool}"
    elif [[ "${OS}" == "Linux" ]]; then
        case "$(detect_linux_distro)" in
            ubuntu|debian) run_privileged apt-get update && run_privileged apt-get install -y "${tool}" ;;
            fedora|rhel)   run_privileged dnf install -y "${tool}" ;;
            arch)          run_privileged pacman -S --noconfirm "${tool}" ;;
            *) return 1 ;;
        esac
    fi
}
```

### Tool-Specific Installation Functions

| Function | Purpose |
|:---------|:--------|
| `ensure_python` | Finds or creates Python virtual environment, installs suite requirements |
| `ensure_cargo` | Installs Rust toolchain via rustup if missing |
| `ensure_homebrew` | Installs Homebrew on macOS if missing |
| `ensure_sshpass` | Installs sshpass for password-based SSH authentication |
| `ensure_jq` | Installs jq for JSON processing |

### Package Manager Abstraction

| Function | Purpose |
|:---------|:--------|
| `can_run_privileged` | Checks if privileged operations are possible (root or sudo available) |
| `run_privileged` | Executes a command with appropriate privilege escalation |
| `detect_linux_distro` | Identifies the Linux distribution for package manager selection |

---
[Back to Overview](./OVERVIEW.md)
