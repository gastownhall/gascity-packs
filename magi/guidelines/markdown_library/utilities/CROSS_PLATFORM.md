# Cross-Platform Compatibility

### OS Detection Pattern

```bash
OS_UNAME="$(uname -s)"
case "$OS_UNAME" in
    Darwin) OS="Darwin" ;;
    Linux) OS="Linux" ;;
    *) echo -e "${RED}ERROR:${NC} Unsupported OS: $OS_UNAME"; exit 1 ;;
esac
```

The suite explicitly supports **macOS (Darwin) and Linux**. Windows support requires WSL or similar POSIX compatibility layer.

### Platform-Specific Considerations

| Platform | Considerations |
|:---------|:---------------|
| **macOS** | Homebrew as primary package manager; BSD `sed` and `date` with different flag syntax; no native `realpath` (handled by `normalize_path_no_deref`); `gdate` from coreutils for nanosecond timestamps |
| **Linux** | Distribution-specific package managers (apt, dnf, pacman, zypper); GNU coreutils assumed; may require sudo for package installation |

### Conditional Implementation

```bash
if [[ "${OS}" == "Darwin" ]]; then
    # macOS-specific implementation
    TIMESTAMP=$(gdate +%s%N 2>/dev/null || echo "$(($(date +%s) * 1000000000))")
else
    # Linux implementation
    TIMESTAMP=$(date +%s%N)
fi
```

---
[Back to Overview](./OVERVIEW.md)
