# State Management and Idempotency

Idempotent operations produce the same result regardless of how many times they execute. Self-healing automation must be idempotent to support retries, restarts, and recovery.

### Idempotency Principles

- **Check-then-act** — Verify current state before acting. Skip action if desired state already exists.
- **Atomic state transitions** — Move from one known state to another atomically. Avoid intermediate states that leave resources partially configured.
- **State persistence** — Record completed operations to prevent re-execution.
- **State verification** — After operations, verify the state matches expectations.

### State Persistence Pattern

```bash
STATE_FILE="/var/lib/myapp/state"
if grep -q "^migration_v2_complete$" "${STATE_FILE}" 2>/dev/null; then
    echo "Migration v2 already complete, skipping"
    return 0
fi
# Run migration
echo "migration_v2_complete" >> "${STATE_FILE}"
```

### Atomic State Transitions

```bash
cat > "${TEMP_FILE}" << EOF
${CONFIG_CONTENT}
EOF
mv "${TEMP_FILE}" "${CONFIG_FILE}"
```

### Lock Management

Prevent concurrent execution when operations are not safe to parallelize:

- **Lock acquisition** — Create lock file atomically. Include PID for stale lock detection.
- **Stale lock detection** — Check if locking process still exists. Remove stale locks from dead processes.
- **Lock release** — Remove lock file in cleanup handlers. Release on both success and failure paths.
- **Lock timeout** — Do not wait indefinitely for locks. Fail fast if lock cannot be acquired within timeout.

### Checkpoint and Resume

Long-running operations should checkpoint progress:
- Record completed phases to persistent storage
- On restart, read checkpoint and resume from last completed phase
- Verify checkpoint integrity before resuming
- Clear checkpoints on successful completion

---
[Back to Overview](./OVERVIEW.md)
