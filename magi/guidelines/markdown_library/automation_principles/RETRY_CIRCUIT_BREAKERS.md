# Retry Strategies and Circuit Breakers

### Retry Strategies

| Strategy | Behavior | Trade-off |
|:---------|:---------|:----------|
| Fixed backoff | Constant wait between retries | Simple but suboptimal for bursty failures |
| Exponential backoff | Double wait time after each failure | Prevents thundering herd; can create long delays |
| Exponential + jitter | Adds randomness to exponential | Distributes retry load across time; preferred for distributed systems |
| Circuit breaker | Stop retrying after repeated failures for a cooldown period | Prevents wasting resources on operations that consistently fail |

**Retry limits are mandatory.** Infinite retry loops transform transient errors into permanent hangs. Define maximum attempts and maximum total wait time.

### Exponential Backoff

```bash
retry_with_exponential_backoff() {
    local max_attempts="${1:-5}"
    local initial_delay="${2:-1}"
    local max_delay="${3:-60}"
    shift 3
    local attempt=1
    local delay="${initial_delay}"
    while (( attempt <= max_attempts )); do
        if "$@"; then
            return 0
        fi
        if (( attempt == max_attempts )); then
            echo "Failed after ${max_attempts} attempts"
            return 1
        fi
        echo "Attempt ${attempt} failed, waiting ${delay}s before retry..."
        sleep "${delay}"
        delay=$(( delay * 2 ))
        (( delay > max_delay )) && delay="${max_delay}"
        ((attempt++))
    done
}
```

### Exponential Backoff with Jitter

```bash
retry_with_jitter() {
    local max_attempts="${1:-5}"
    local base_delay="${2:-1}"
    shift 2
    local attempt=1
    while (( attempt <= max_attempts )); do
        if "$@"; then
            return 0
        fi
        if (( attempt == max_attempts )); then
            return 1
        fi
        local delay=$(( base_delay * (2 ** (attempt - 1)) ))
        local jitter=$(( RANDOM % delay ))
        sleep $(( delay + jitter ))
        ((attempt++))
    done
}
```

### Circuit Breaker

States: **closed** (normal operation), **open** (failures exceeded threshold; requests fail immediately), **half-open** (test single request after cooldown).

```bash
CIRCUIT_STATE="/var/lib/myapp/circuit_state"
FAILURE_THRESHOLD=5
COOLDOWN_PERIOD=300

circuit_breaker_call() {
    local service="$1"
    shift
    if [[ -f "${CIRCUIT_STATE}/${service}.open" ]]; then
        local open_time
        open_time=$(stat -c %Y "${CIRCUIT_STATE}/${service}.open" 2>/dev/null || echo 0)
        local current_time
        current_time=$(date +%s)
        local elapsed=$((current_time - open_time))
        if (( elapsed < COOLDOWN_PERIOD )); then
            echo "Circuit breaker OPEN for ${service} (${elapsed}s elapsed)"
            return 1
        fi
        mv "${CIRCUIT_STATE}/${service}.open" "${CIRCUIT_STATE}/${service}.halfopen"
    fi
    if "$@"; then
        rm -f "${CIRCUIT_STATE}/${service}."* 2>/dev/null
        return 0
    fi
    local failures
    failures=$(cat "${CIRCUIT_STATE}/${service}.failures" 2>/dev/null || echo 0)
    ((failures++))
    if (( failures >= FAILURE_THRESHOLD )); then
        touch "${CIRCUIT_STATE}/${service}.open"
        rm -f "${CIRCUIT_STATE}/${service}.failures"
        echo "Circuit breaker OPENED for ${service} after ${failures} failures"
    else
        echo "${failures}" > "${CIRCUIT_STATE}/${service}.failures"
    fi
    return 1
}
```

---
[Back to Overview](./OVERVIEW.md)
