# Logging

### SLF4J as the Logging Facade

Bind to Logback or Log4j2. **Never use `java.util.logging` (JUL), `System.out.println`, or `System.err.println`** for application logging.

### Parameterized Log Messages

```java
// CORRECT — parameters evaluated only when level enabled
log.debug("User {} placed order {}", userId, orderId);

// FORBIDDEN — concatenation runs even when debug disabled
log.debug("User " + userId + " placed order " + orderId);
```

At scale, debug log statements in hot paths add measurable overhead with concatenation.

### MDC for Request-Scoped Context

```java
MDC.put("requestId", requestId);
MDC.put("userId", userId);
try {
    // process request
} finally {
    MDC.clear();   // prevent leakage in thread pools
}
```

Set MDC values at the request entry point (servlet filter, message consumer). Include MDC values in the log pattern. Clear MDC at request completion.

### Log Levels

| Level | Use |
|:------|:----|
| ERROR | Operation failed, requires investigation |
| WARN | Unexpected condition, degraded functionality |
| INFO | Significant business events (order placed, payment processed) |
| DEBUG | Detailed operational flow for development debugging |
| TRACE | Extremely detailed, method-level tracing |

Production runs at INFO. DEBUG/TRACE enabled per-component for targeted troubleshooting.

---
[Back to Overview](./OVERVIEW.md)
