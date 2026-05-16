# Network and Connectivity

Network operations are inherently unreliable. Self-healing automation treats network failures as expected conditions rather than exceptional cases.

### Connectivity Verification

```bash
verify_connectivity() {
    local host="$1"
    local port="$2"
    local timeout="${3:-5}"
    if command -v nc >/dev/null 2>&1; then
        nc -z -w "${timeout}" "${host}" "${port}" 2>/dev/null
    elif command -v timeout >/dev/null 2>&1; then
        timeout "${timeout}" bash -c "echo >/dev/tcp/${host}/${port}" 2>/dev/null
    else
        return 0  # Cannot verify; proceed optimistically
    fi
}
```

### DNS Resolution

DNS failures are common and recoverable:
- Retry DNS lookups with backoff
- Consider caching successful resolutions
- Fall back to IP addresses when available
- Use multiple DNS servers when primary fails

### HTTP Operations

- Set explicit timeouts for connection and read operations
- Handle redirects appropriately (follow or fail based on security requirements)
- Verify SSL/TLS certificates in production
- Parse response codes and handle each class appropriately
- Extract error details from response bodies when available

### Download Operations

- Verify available disk space before downloading
- Support resume for interrupted downloads
- Verify checksums after download completes
- Use mirrors when primary sources are unavailable
- Clean up partial downloads on failure

### Proxy Configuration

Corporate environments often require proxies:
- Respect `HTTP_PROXY`, `HTTPS_PROXY`, `NO_PROXY` environment variables
- Support proxy authentication
- Handle proxy failures as network failures
- Document proxy requirements for environments where automation runs

---
[Back to Overview](./OVERVIEW.md)
