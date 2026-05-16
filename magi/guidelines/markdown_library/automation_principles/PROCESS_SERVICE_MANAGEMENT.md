# Process and Service Management

### Process Lifecycle

- **Starting processes** — Verify successful start. Check process exists after start. Verify expected behavior (port listening, health endpoint responding).
- **Stopping processes** — Send graceful termination first (SIGTERM). Wait for graceful shutdown. Force kill (SIGKILL) if graceful fails after timeout.
- **Process status** — Verify processes are running before operations that depend on them. Handle processes that have died unexpectedly.

### Service Management

| Init System | Tool |
|:------------|:-----|
| systemd | `systemctl` (most modern Linux) |
| OpenRC | `rc-service`, `rc-update` (Alpine, Gentoo) |
| launchd | `launchctl` (macOS) |
| Docker/containers | Manage processes directly; no init |

Detect the available service manager and use appropriate commands.

### Background Process Management

- Store PID in known location for later management
- Verify process is still running periodically
- Restart automatically if process dies unexpectedly
- Log restarts and death reasons
- **Prevent restart loops for persistently failing processes**

### Signal Handling

| Signal | Treatment |
|:-------|:----------|
| SIGTERM | Graceful shutdown request — clean up and exit |
| SIGINT | Interactive interrupt (Ctrl+C) — treat as SIGTERM |
| SIGHUP | Configuration reload — reload without restart |
| SIGUSR1/SIGUSR2 | Application-defined (log rotation, status dump) |

Register signal handlers early. Execute cleanup logic in handlers. Exit with appropriate code.

```bash
cleanup() {
    echo "Received shutdown signal, cleaning up..."
    [[ -n "${BACKGROUND_PID}" ]] && kill -TERM "${BACKGROUND_PID}" 2>/dev/null
    rm -rf "${TEMP_DIR}"
    [[ -n "${LOCKFILE}" ]] && rm -f "${LOCKFILE}"
    echo "Cleanup complete"
    exit 0
}
trap cleanup SIGTERM SIGINT SIGHUP
```

---
[Back to Overview](./OVERVIEW.md)
