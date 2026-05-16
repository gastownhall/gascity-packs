# Version Deltas Within 8.1.x

| Version Range | Constraint |
|:--------------|:-----------|
| 8.1.0–8.1.32 | Java 11 |
| 8.1.33+ | Java 17 |
| 8.1.17+ | `EventBus` deprecated in favor of `EventManager` (interface-compatible). `EventBus` removed entirely in 8.3 |

### JDK 17 Strong Encapsulation

JDK 17 strongly encapsulates internals. Audit `setAccessible(true)` calls into non-public JDK classes; declare `--add-opens` / `--add-exports` in:

| File | Scope |
|:-----|:------|
| `ignition.conf` | Gateway |
| `lib/runtime/client-opens.conf` | Vision Client |
| `data/client-opens.conf` | Vision Designer |

---
[Back to Overview](./OVERVIEW.md)
