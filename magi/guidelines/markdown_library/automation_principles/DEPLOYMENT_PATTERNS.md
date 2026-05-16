# Deployment Automation Patterns

### Blue-Green Deployment

Deploy to inactive environment; switch traffic after validation.

```text
Phase 1: Deploy to blue environment while green serves traffic
Phase 2: Validate blue deployment with smoke tests
Phase 3: Switch traffic from green to blue
Phase 4: Keep green as rollback target
```

### Canary Deployment

Gradually roll out changes to subset of users.

```text
Phase 1: Deploy to canary instances (5-10% of fleet)
Phase 2: Monitor metrics and error rates
Phase 3: Gradually increase canary traffic
Phase 4: Full rollout or rollback based on metrics
```

### Rolling Deployment

```bash
rolling_deploy() {
    local instances=("$@")
    local batch_size="${BATCH_SIZE:-1}"
    for ((i=0; i<${#instances[@]}; i+=batch_size)); do
        local batch=("${instances[@]:i:batch_size}")
        for instance in "${batch[@]}"; do
            echo "Draining traffic from ${instance}..."
            drain_traffic "${instance}"
            echo "Deploying to ${instance}..."
            deploy_to_instance "${instance}"
            echo "Health checking ${instance}..."
            if ! wait_for_healthy "${instance}"; then
                echo "Deployment failed on ${instance}, rolling back..."
                rollback_instance "${instance}"
                return 1
            fi
            echo "Enabling traffic to ${instance}..."
            enable_traffic "${instance}"
        done
        echo "Waiting for stabilization..."
        sleep "${STABILIZATION_PERIOD:-30}"
    done
}
```

---
[Back to Overview](./OVERVIEW.md)
