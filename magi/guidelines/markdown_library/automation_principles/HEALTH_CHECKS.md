# Health Checks

### Startup Health Check

```bash
wait_for_healthy() {
    local service_url="$1"
    local max_wait="${2:-60}"
    local start_time
    start_time=$(date +%s)
    while true; do
        if curl -sf "${service_url}/health" >/dev/null 2>&1; then
            echo "Service is healthy"
            return 0
        fi
        local elapsed=$(( $(date +%s) - start_time ))
        if (( elapsed >= max_wait )); then
            echo "Service failed to become healthy within ${max_wait}s"
            return 1
        fi
        echo "Waiting for service to become healthy (${elapsed}s elapsed)..."
        sleep 2
    done
}
```

### Liveness Probe

```bash
liveness_check() {
    local pid="$1"
    local health_endpoint="$2"
    if ! kill -0 "${pid}" 2>/dev/null; then
        return 1
    fi
    if [[ -n "${health_endpoint}" ]]; then
        curl -sf "${health_endpoint}" >/dev/null 2>&1
    fi
}
```

### Readiness Probe

```bash
readiness_check() {
    local service_url="$1"
    if ! nc -z "$(echo "${service_url}" | cut -d: -f1)" "$(echo "${service_url}" | cut -d: -f2)" 2>/dev/null; then
        return 1
    fi
    curl -sf "${service_url}/ready" >/dev/null 2>&1
}
```

---
[Back to Overview](./OVERVIEW.md)
