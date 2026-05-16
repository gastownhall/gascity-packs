# Monitoring and Metrics

```nginx
location = /nginx_status {
    stub_status;
    access_log off;
    allow 127.0.0.1;
    deny  all;
}
```

Exposes active connections, accepts, handled connections, and request counts. Feed into Prometheus (via `nginx-exporter`), Datadog, or equivalent.

### Alerting Thresholds

| Metric | Threshold | Severity |
|:-------|:----------|:---------|
| 5xx error rate | > 1% | Critical |
| Average upstream response time | Above SLA | Warning |
| Active connection count | Approaching `worker_connections` limit | Warning |
| Certificate expiry | < 14 days | Critical |

### NGINX Plus

For NGINX Plus, enable the API module for detailed real-time metrics: per-upstream server connection counts, health status, response times, and request rates. Export via the NGINX Plus API or Prometheus exporter.

### External Auditing

Periodically audit configuration and TLS health using external scanners:

- SSL Labs (`ssllabs.com/ssltest`) for TLS grading.
- Mozilla Observatory for header security.
- Custom scripts that verify expected directives are present and correctly valued.

---
[Back to Overview](./OVERVIEW.md)
