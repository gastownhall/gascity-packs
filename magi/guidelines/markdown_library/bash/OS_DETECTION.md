# OS and Distribution Detection

### Linux Distro Helper
Use `if/elif` for filesystem condition testing — not `case`. The `ID` value from `/etc/os-release` is then dispatched with `case` for value matching:
```bash
detect_distro() {
    [[ -f /etc/os-release ]] && { . /etc/os-release; printf '%s\n' "${ID}"; return 0; }
    [[ -f /etc/debian_version ]] && { printf '%s\n' "debian"; return 0; }
    [[ -f /etc/redhat-release ]] && { printf '%s\n' "rhel"; return 0; }
    printf '%s\n' "unknown"
    return 0
}
```

### Branching Discipline
All distro branching uses `case` with explicit unknown handling:
```bash
case "${distro}" in
    ubuntu|debian|linuxmint|pop) apt_install "$@" ;;
    fedora|rhel|centos|rocky|almalinux) dnf_install "$@" ;;
    arch|manjaro) pacman_install "$@" ;;
    opensuse|sles) zypper_install "$@" ;;
    *) printf 'ERROR: Unsupported distro: %s\n' "${distro}" >&2; exit 1 ;;
esac
```

### Cross-Platform Command Differences
| Command | macOS | Linux |
|---------|-------|-------|
| `sed -i` | requires empty arg: `sed -i ''` | direct: `sed -i` |
| `readlink -f` | not available — use `cd -P && pwd` | available |
| `date` | different flag syntax | GNU flags |
| `stat` | `-f` for format | `-c` for format |

Branch on `${OS}` when behavior differs:
```bash
if [[ "${OS}" == "Darwin" ]]; then
    sed -i '' 's/old/new/' file
else
    sed -i 's/old/new/' file
fi
```

### POSIX Compliance Preferences
- Use `[[ ]]` for tests (Bash-specific, more reliable than `[ ]`).
- Use `$(command)` not backticks.
- Use `printf` not `echo`.

---
[Back to Overview](./OVERVIEW.md)
