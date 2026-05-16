# Cross-Platform Considerations

### Shell Compatibility

- **POSIX compliance** — Prefer POSIX shell features for maximum compatibility. Avoid bashisms when portability matters.
- **Bash features** — When using bash-specific features, require bash explicitly with `#!/usr/bin/env bash` and verify bash version.
- **macOS considerations** — macOS ships with bash 3.x (GPLv2) by default. Features like associative arrays require bash 4+, which must be installed separately.

### Tool Availability

| Task | Linux | macOS | Most-portable Alternative |
|:-----|:------|:------|:--------------------------|
| Download | curl, wget | curl | curl |
| JSON parsing | jq | jq (install) | `python -m json.tool` |
| Text processing | sed, awk | BSD sed, awk | perl |
| Process listing | `ps aux` | `ps aux` | Compatible across both |
| Network tools | ss, ip | netstat | netstat (deprecated but universal) |

### Path Differences

| Path | Linux | macOS |
|:-----|:------|:------|
| Homebrew | — | `/opt/homebrew` (ARM), `/usr/local` (Intel) |
| Configuration | `/etc` | `/usr/local/etc` (Homebrew) |
| User data | `$HOME/.local` | `$HOME/Library` |

Use environment variables and detection rather than hardcoded paths.

### Package Management

| Platform | Manager | Install Command |
|:---------|:--------|:----------------|
| Debian/Ubuntu | apt | `apt-get install -y` |
| RHEL/Fedora | dnf | `dnf install -y` |
| Alpine | apk | `apk add --no-cache` |
| Arch | pacman | `pacman -S --noconfirm` |
| macOS | brew | `brew install` |

Detect the platform and use the appropriate package manager.

---
[Back to Overview](./OVERVIEW.md)
