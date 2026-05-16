# Lifecycle Management

### Container States

- **stopped** — not running; no resources consumed.
- **running** — active; resources allocated and in use.
- **paused** — frozen; processes suspended but memory retained.

State transitions:

```bash
pct start 101
pct stop 101
pct shutdown 101  # Graceful ACPI shutdown
pct reboot 101
pct suspend 101
pct resume 101
```

### Boot Order and Dependencies

```ini
onboot: 1
startup: order=10,up=30,down=60
```

| Parameter | Purpose |
|:----------|:--------|
| `order` | Lower numbers start first, stop last |
| `up` | Delay in seconds after starting before starting next container |
| `down` | Timeout for graceful shutdown before forced stop |

| Order Range | Use |
|:------------|:----|
| 1–10 | Infrastructure (DNS, storage services) |
| 11–50 | Databases and backends |
| 51–90 | Application servers |
| 91–99 | Edge services and load balancers |

### Template Conversion

```bash
pct template 101
```

Templated containers cannot be started; they serve as clone sources only. **The operation is irreversible** — backup first if the original must be preserved.

### Cloning

```bash
# Full clone — independent copy, no dependency on source
pct clone 9001 102 --full --hostname new-host --storage local-lvm
# Linked clone — copy-on-write from source; space efficient but dependent
pct clone 9001 102 --hostname new-host
```

Linked clones are suitable for development and testing; full clones for production workloads.

### Destruction

Container removal is permanent:

```bash
pct stop 101
pct destroy 101
pct destroy 101 --purge  # Also remove unreferenced volumes
```

Protect important containers:

```bash
pct set 101 --protection 1
```

Protected containers cannot be removed without explicitly clearing the protection flag.

---
[Back to Overview](./OVERVIEW.md)
