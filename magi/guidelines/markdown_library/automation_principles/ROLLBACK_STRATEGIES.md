# Rollback Strategies

### Automatic Rollback Triggers

- Health check failures exceed threshold
- Error rate exceeds baseline
- Response time degrades beyond SLA

```bash
deploy_with_rollback() {
    local version="$1"
    local previous_version
    previous_version=$(get_current_version)
    create_backup "${previous_version}"
    if ! deploy_version "${version}"; then
        echo "Deployment failed, initiating rollback..."
        restore_backup "${previous_version}"
        return 1
    fi
    local monitor_duration=300
    local start_time
    start_time=$(date +%s)
    while (( $(date +%s) - start_time < monitor_duration )); do
        if ! health_check; then
            echo "Health check failed, rolling back..."
            restore_backup "${previous_version}"
            return 1
        fi
        local error_rate
        error_rate=$(get_error_rate)
        if (( $(echo "${error_rate} > 5" | bc -l) )); then
            echo "Error rate too high (${error_rate}%), rolling back..."
            restore_backup "${previous_version}"
            return 1
        fi
        sleep 10
    done
    echo "Deployment successful and stable"
}
```

### Database Rollback

- Use forward-only migrations with compensating transactions
- Backup before migration, restore on failure
- Use feature flags to disable new code paths

---
[Back to Overview](./OVERVIEW.md)
