# Dependency Management

### Auto-Installation Required
Scripts must attempt to install missing dependencies. Never simply fail on missing dependency — always try installation before failing.

### Detection → Install → Verify Pattern
```bash
ensure_jq() {
    command -v jq >/dev/null 2>&1 && return 0
    printf '%b\n' "${FG_B}Installing jq...${RST}"
    case "${OS}" in
        Darwin) brew install jq ;;
        Linux)
            local distro
            distro="$(detect_distro)"
            case "${distro}" in
                ubuntu|debian) run_privileged apt-get install -y jq ;;
                *) return 1 ;;
            esac ;;
    esac
    command -v jq >/dev/null 2>&1
}
```

### Fallback Chain (mandatory order)
- **macOS**: Homebrew → version manager → direct download.
- **Linux**: native package manager → official repo → version manager → direct download → build from source.

### Early Sudo Authentication
If ANY part of a script requires sudo/root, the script MUST prompt for sudo credentials at the very start.
```bash
require_sudo() {
    can_run_privileged || { printf '%s\n' "ERROR: sudo not available" >&2; exit 3; }
    if [[ $EUID -ne 0 ]]; then
        printf '%b\n' "${FG_B}Authenticating sudo (required)...${RST}"
        sudo -v || { printf '%s\n' "ERROR: sudo authentication failed" >&2; exit 3; }
    fi
    return 0
}
```

---
[Back to Overview](./OVERVIEW.md)
