# Container Testing

### Integration Tests

```yaml
- name: Test container
  run: |
    docker run -d --name test myapp:test
    docker exec test npm test
    docker logs test
```

### Testcontainers Pattern

```csharp
var postgres = new ContainerBuilder()
    .WithImage("postgres:16")
    .WithEnvironment("POSTGRES_PASSWORD", "test")
    .WithWaitStrategy(Wait.ForUnixContainer().UntilPortIsAvailable(5432))
    .Build();
await postgres.StartAsync();
```

Testcontainers libraries exist for Java, .NET, Python, Go, Node.js, and Rust.

---
[Back to Overview](./OVERVIEW.md)
