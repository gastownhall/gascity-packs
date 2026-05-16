# Secrets API

Dynamic secrets management replacing 8.1 `EncodedStringField`.

### SecretConfig

```java
public record DatabaseConnection(
        String url,
        String username,
        SecretConfig password,    // ← stored on the resource record
        int maxPoolSize) { ... }
```

| Variant | Description |
|:--------|:------------|
| `SecretConfig.Inline` | Encoded inline in the resource record |
| `SecretConfig.Referenced` | Named secret in a `SecretProvider` |
| `SecretConfig.EMPTY` | Default/unset |

The Gson serializer handles all variants transparently.

### Secret Instance Lifecycle

```java
Secret<?> secret = Secret.create(gatewayContext, secretConfig);

try (Plaintext pt = secret.getPlaintext()) {
    String value = pt.getAsString(StandardCharsets.UTF_8);
    // use value within try-with-resources block
}
// pt.close() zeroes the backing array on exit
```

| Constraint | Detail |
|:-----------|:-------|
| Hold what | Hold the `Secret<?>` instance, NOT the resolved plaintext. The `Secret` is a lazy accessor that picks up rotations |
| Fetch | `try (Plaintext pt = secret.getPlaintext()) { ... }` — `Plaintext.close()` zeroes the backing array |
| Char arrays | Prefer `pt.getAsCharArray()` over `getAsString` when the consuming API accepts `char[]`; manually fill with `'\0'` after use |

### SecretReferenceProperty

Declares a `SecretConfig.Referenced` field's reference relationship so renames and deletes of the referenced `SecretProvider` propagate.

```java
SecretReferenceProperty<DatabaseConnection> passwordRef =
    SecretReferenceProperty.<DatabaseConnection>builder()
        .setGetSecretConfigFunction(DatabaseConnection::password)
        .setUpdateSecretConfigFunction(DatabaseConnection::withPassword)
        .build();

addReferenceProperty("password", passwordRef);   // inside extension point ctor or buildReferenceDelegate
```

### Migrating from EncodedStringField

| Path | API |
|:-----|:----|
| Automatic | `DefaultRecordEncodingDelegate` — recognizes the old encoded format and lazily migrates to `SecretConfig.Inline` as resources load. **No data migration tooling required.** |
| Custom encoding | `SecretConfig.GsonAdapter` directly |

### Forbidden

- **Never cache plaintext as a `String` or `char[]` field** — defeats rotation and prolongs in-memory exposure.
- **Never log `Plaintext` content** at any level.
- **Never store secrets in `module.xml`, JAR resources, `gradle.properties`, or version control.**

---
[Back to Overview](./OVERVIEW.md)
