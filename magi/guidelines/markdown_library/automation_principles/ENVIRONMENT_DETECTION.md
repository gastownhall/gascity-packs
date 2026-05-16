# Environment Detection and Adaptation

Automation must adapt to the environment it finds rather than assume a specific environment exists. Operating system, distribution, available tools, network topology, and privilege level all vary across execution contexts.

### Operating System Detection

```bash
OS="$(uname -s)"
case "${OS}" in
    Darwin) # macOS-specific paths and tools ;;
    Linux)  # Linux-specific paths and tools ;;
    MINGW*|CYGWIN*|MSYS*) # Windows environments ;;
    *) echo "Unsupported OS: ${OS}"; exit 1 ;;
esac
```

### Linux Distribution Detection

```bash
if [[ -f /etc/os-release ]]; then
    . /etc/os-release
    DISTRO="${ID}"
    DISTRO_VERSION="${VERSION_ID}"
elif [[ -f /etc/debian_version ]]; then
    DISTRO="debian"
elif [[ -f /etc/redhat-release ]]; then
    DISTRO="rhel"
else
    DISTRO="unknown"
fi
```

### Privilege Level Detection

```bash
if [[ $EUID -eq 0 ]]; then
    PRIV_CMD=""
elif command -v sudo >/dev/null 2>&1; then
    PRIV_CMD="sudo"
elif command -v doas >/dev/null 2>&1; then
    PRIV_CMD="doas"
else
    echo "Root privileges required but no elevation mechanism available"
    exit 1
fi
```

### Container Detection

```bash
is_container() {
    [[ -f /.dockerenv ]] || \
    [[ -f /run/.containerenv ]] || \
    grep -q 'docker\|lxc\|kubepods' /proc/1/cgroup 2>/dev/null
}
```

Inside containers, avoid service management commands (`systemctl`), kernel module operations, and assumptions about filesystem persistence.

### CI/CD Environment Detection

```bash
is_ci() {
    [[ -n "${CI:-}" ]] || \
    [[ -n "${GITHUB_ACTIONS:-}" ]] || \
    [[ -n "${GITLAB_CI:-}" ]] || \
    [[ -n "${JENKINS_URL:-}" ]] || \
    [[ -n "${BUILDKITE:-}" ]]
}
```

In CI, assume no interactive input, optimize for build cache utilization, and output machine-parseable formats when appropriate.

### Architecture Detection

```bash
ARCH="$(uname -m)"
case "${ARCH}" in
    x86_64|amd64) ARCH_NORMALIZED="amd64" ;;
    aarch64|arm64) ARCH_NORMALIZED="arm64" ;;
    armv7l) ARCH_NORMALIZED="armv7" ;;
    *) echo "Unsupported architecture: ${ARCH}"; exit 1 ;;
esac
```

### Environment-Specific Defaults

| Environment | Defaults |
|:------------|:---------|
| macOS | Homebrew paths, no systemd |
| Ubuntu/Debian | apt, systemd |
| RHEL/Fedora | dnf, SELinux |
| Alpine | apk, musl instead of glibc |
| Containers | No service management, env vars for configuration |
| CI | Verbose logging, no interactive prompts |

---
[Back to Overview](./OVERVIEW.md)
