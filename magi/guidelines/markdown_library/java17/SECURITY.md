# Security

### Validate All External Input

Use Bean Validation (Jakarta Validation / Hibernate Validator):

```java
public record CreateOrderRequest(
    @NotNull UUID customerId,
    @NotNull @Size(min = 1, max = 100) List<LineItem> items,
    @Pattern(regexp = "[A-Z]{3}") String currency,
    @Min(0) BigDecimal couponAmount) {}
```

Validate at the service boundary before processing.

### PreparedStatement for All SQL

```java
try (var stmt = conn.prepareStatement(
        "SELECT * FROM users WHERE email = ? AND tenant = ?")) {
    stmt.setString(1, email);
    stmt.setString(2, tenant);
    try (var rs = stmt.executeQuery()) { ... }
}
```

String concatenation into SQL is a SQL injection vulnerability regardless of input sanitization. Applies to JDBC, JPA native queries, and any framework that generates SQL.

### Avoid Java Serialization for New Code

Java deserialization is one of the most exploited vulnerability classes in the JVM ecosystem. Deserialization of untrusted data enables remote code execution. Use JSON (Jackson, Gson), Protocol Buffers, Avro, or MessagePack.

If Java serialization is required for legacy compatibility, use serialization filters (`ObjectInputFilter`, JEP 415 in Java 17) with a strict allowlist:

```java
ObjectInputFilter filter = ObjectInputFilter.Config.createFilter(
    "com.acme.dto.*;com.acme.events.*;!*");
ObjectInputFilter.Config.setSerialFilter(filter);
```

### Strong Cryptographic Algorithms

| Use | Algorithm |
|:----|:----------|
| Symmetric encryption | AES-256-GCM |
| Asymmetric | RSA-2048+ or ECDSA P-256+ |
| Hashing | SHA-256+ |
| Password hashing | bcrypt or Argon2 |
| Random for crypto | `java.security.SecureRandom` — **never `java.util.Random`** |

Forbidden: MD5, SHA-1, DES, 3DES, RC4.

### Do Not Log Sensitive Data

Passwords, tokens, credit card numbers, SSNs, API keys. Sanitize log messages at the point of logging. Use structured logging (SLF4J + Logback/Log4j2) with MDC for context. Configure log frameworks to redact known sensitive patterns.

### Strong JDK Encapsulation (JEP 403)

Java 17 strongly encapsulates JDK internals by default. Code using `--add-opens` or `--add-exports` is accessing unstable internal APIs. Migrate away from internal APIs. Reflection into JDK internals that worked in Java 8/11 may fail silently or throw `InaccessibleObjectException` in Java 17.

---
[Back to Overview](./OVERVIEW.md)
