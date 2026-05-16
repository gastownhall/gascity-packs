# Feature Flag Integration

### Feature Flag Check with Caching

```bash
check_feature_flag() {
    local feature="$1"
    local flag_service="${FLAG_SERVICE_URL:-http://flags.internal}"
    local cache_file="/tmp/flags_${feature}.cache"
    local cache_ttl=60
    if [[ -f "${cache_file}" ]]; then
        local cache_age=$(( $(date +%s) - $(stat -c %Y "${cache_file}") ))
        if (( cache_age < cache_ttl )); then
            cat "${cache_file}"
            return
        fi
    fi
    local response
    response=$(curl -sf "${flag_service}/flags/${feature}" 2>/dev/null || echo '{"enabled":false}')
    echo "${response}" > "${cache_file}"
    echo "${response}" | jq -r '.enabled'
}

if [[ "$(check_feature_flag 'new_algorithm')" == "true" ]]; then
    run_new_algorithm
else
    run_legacy_algorithm
fi
```

### Percentage Rollout

```bash
should_enable_feature() {
    local feature="$1"
    local user_id="$2"
    local percentage="${3:-0}"
    local hash
    hash=$(echo -n "${feature}:${user_id}" | sha256sum | cut -d' ' -f1)
    local bucket=$(( 0x${hash:0:8} % 100 ))
    [[ ${bucket} -lt ${percentage} ]]
}
```

---
[Back to Overview](./OVERVIEW.md)
