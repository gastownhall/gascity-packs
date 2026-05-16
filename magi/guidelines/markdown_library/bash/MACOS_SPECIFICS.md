# Homebrew and macOS Tool Preference

On macOS, many system-bundled tools are ancient. When a Homebrew version exists, always use it. This applies to `rsync`, `grep`, `sed`, `awk`, `coreutils`, `curl`, and `git`.

### Always Prefer Homebrew Packages
```bash
# Correct: explicit Homebrew rsync invocation
/opt/homebrew/bin/rsync -aHAX --delete --partial /source/ /dest/
```

Forbidden:
- Relying on `/usr/bin/rsync` on macOS (v2.6.9, 2006).
- Relying on `/usr/bin/grep` on macOS for advanced features (missing `-P`).
- Relying on `/usr/bin/sed` on macOS (incompatible `-i` behavior).

### Do Not Mix Implementations Mid-Workflow
When a script uses a Homebrew tool, all related remote sides and pipelines must use a compatible version. Always specify the binary path explicitly:
```bash
if [[ "${OS}" == "Darwin" ]]; then
    RSYNC="/opt/homebrew/bin/rsync"
    [[ -x "${RSYNC}" ]] || { printf 'ERROR: Homebrew rsync not installed\n' >&2; exit 3; }
else
    RSYNC="rsync"
fi
readonly RSYNC
```

### macOS Extended Attributes Awareness
macOS system `rsync` uses `-E` for resource forks. Homebrew `rsync` uses Linux-style `-A` and `-X`. Document which `rsync` version your flags target.

---
[Back to Overview](./OVERVIEW.md)
