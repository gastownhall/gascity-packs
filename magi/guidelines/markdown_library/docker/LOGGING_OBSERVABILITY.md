# Logging and Observability

### Logging Strategy

Applications in containers must log to stdout/stderr. Docker captures these streams and routes them through the configured logging driver. Writing logs to files inside containers is prohibited — they are lost on container removal and complicate log aggregation.

```dockerfile
ENV PYTHONUNBUFFERED=1
```

### Logging Drivers

Configure logging driver at daemon or container level:

```bash
docker run --log-driver=json-file --log-opt max-size=10m --log-opt max-file=3 myimage
```

Common drivers:
- **json-file**: Default; local JSON files; requires rotation
- **local**: Optimized local storage with automatic rotation
- **syslog**: Forward to syslog server
- **fluentd**: Forward to Fluentd collector
- **awslogs**: Forward to CloudWatch Logs
- **gcplogs**: Forward to Google Cloud Logging

Fluentd in Compose:
```yaml
services:
  app:
    logging:
      driver: fluentd
      options:
        fluentd-address: localhost:24224
        tag: docker.{{.Name}}
```

Daemon-level rotation defaults:
```json
{
  "log-driver": "local",
  "log-opts": {
    "max-size": "10m",
    "max-file": "5",
    "compress": "true"
  }
}
```

Required: max log file size 50m, max 5 files retained.

### Log Format

Emit structured logs (JSON) for machine parsing:

```json
{
  "timestamp": "2024-01-20T10:30:00Z",
  "level": "info",
  "message": "\nRequest processed",
  "request_id": "abc123",
  "duration_ms": 45,
  "container_id": "${HOSTNAME}",
  "service": "api"
}
```

Include:
- ISO 8601 timestamp
- Log level
- Message
- Correlation IDs (request ID, trace ID)
- Relevant context fields

### Metrics and Tracing

- Expose Prometheus metrics endpoint for scraping.
- Instrument with OpenTelemetry for distributed tracing.
- Use sidecar pattern for metrics collection agents when needed.
- Health and readiness endpoints separate from metrics.

---
[Back to Overview](./OVERVIEW.md)
