# Exception Handling

### Checked vs Unchecked

| Kind | Use For |
|:-----|:--------|
| Checked (`Exception`) | Recoverable conditions where the caller can take meaningful action — `IOException`, `SQLException`, custom business exceptions (`InsufficientFundsException`, `OrderNotFoundException`) |
| Unchecked (`RuntimeException`) | Programming errors — `IllegalArgumentException`, `IllegalStateException`, `NullPointerException`, `IndexOutOfBoundsException` |

Do not use checked exceptions for conditions the caller cannot recover from.

### Never Catch Exception or Throwable Broadly

Forbidden except at the top-level entry point (main method, request handler, message consumer). Broad catches:

- Hide bugs (catching `NullPointerException` silently).
- Mask errors (catching `InterruptedException` without re-interrupting).
- Prevent proper recovery logic.

Catch the most specific exception type that the operation can produce.

### Re-Interrupt on InterruptedException

```java
try {
    queue.take();
} catch (InterruptedException e) {
    Thread.currentThread().interrupt();
    throw new ServiceShutdownException(e);
}
```

Never swallow `InterruptedException` — prevents the thread from responding to shutdown signals, causing executors and application shutdown to hang.

### try-with-resources for AutoCloseable

```java
try (var conn = dataSource.getConnection();
     var stmt = conn.prepareStatement(sql);
     var rs = stmt.executeQuery()) {
    while (rs.next()) {
        // process
    }
}
```

Guarantees cleanup on both normal completion and exception, handles suppressed exceptions correctly.

### Custom Exception Hierarchies

Single base exception per module or service:

```java
public class PaymentServiceException extends RuntimeException { ... }
public class PaymentDeclinedException extends PaymentServiceException { ... }
public class PaymentTimeoutException extends PaymentServiceException { ... }
```

### Context in Exception Messages

```java
// FORBIDDEN — bare message
throw new OrderNotFoundException("Order not found");

// CORRECT — context
throw new OrderNotFoundException(
    "Order not found: orderId=" + orderId + " customerId=" + customerId,
    cause);
```

Pass the causing exception as the second argument to preserve the full stack trace chain.

---
[Back to Overview](./OVERVIEW.md)
