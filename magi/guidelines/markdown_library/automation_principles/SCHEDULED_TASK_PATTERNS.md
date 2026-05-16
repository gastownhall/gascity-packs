# Scheduled Task Patterns

### Cron-Safe with Locking

```bash
#!/bin/bash
LOCKFILE="/var/lock/mytask.lock"
LOCKFD=99
acquire_lock() {
    eval "exec ${LOCKFD}>${LOCKFILE}"
    flock -n ${LOCKFD} || {
        echo "Another instance is already running"
        exit 0
    }
    echo $$ > "${LOCKFILE}"
}
release_lock() {
    flock -u ${LOCKFD}
    rm -f "${LOCKFILE}"
}
acquire_lock
trap release_lock EXIT
run_scheduled_task
```

### Schedule with Jitter

Prevents thundering herd:

```bash
JITTER=$(( RANDOM % 300 ))
echo "Delaying execution by ${JITTER} seconds to prevent thundering herd"
sleep "${JITTER}"
run_task
```

### Schedule Monitoring

```bash
monitored_cron_job() {
    local job_name="$1"
    local heartbeat_url="${MONITORING_URL}/heartbeat/${job_name}"
    curl -X POST "${heartbeat_url}/start" 2>/dev/null
    if run_actual_job; then
        curl -X POST "${heartbeat_url}/success" 2>/dev/null
    else
        curl -X POST "${heartbeat_url}/failure" \
             -d "error=$?" \
             -d "output=$(tail -n 100 /var/log/${job_name}.log)" \
             2>/dev/null
        exit 1
    fi
}
```

---
[Back to Overview](./OVERVIEW.md)
