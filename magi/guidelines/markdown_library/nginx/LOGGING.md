# Logging and Observability

NGINX access and error logs provide request-level visibility for debugging, security monitoring, and performance analysis. **Structured logging enables integration with log aggregation and SIEM systems.**

### Structured JSON Log Format

```nginx
log_format json_combined escape=json
  '{'
    '"time":"$time_iso8601",'
    '"remote_addr":"$remote_addr",'
    '"method":"$request_method",'
    '"uri":"$request_uri",'
    '"http_version":"$server_protocol",'
    '"status":$status,'
    '"body_bytes_sent":$body_bytes_sent,'
    '"referrer":"$http_referer",'
    '"user_agent":"$http_user_agent",'
    '"request_time":$request_time,'
    '"upstream_response_time":"$upstream_response_time",'
    '"upstream_addr":"$upstream_addr",'
    '"ssl_protocol":"$ssl_protocol",'
    '"ssl_cipher":"$ssl_cipher"'
  '}';

access_log /var/log/nginx/access.log json_combined;
error_log  /var/log/nginx/error.log warn;
```

JSON logs parse directly into Elasticsearch, Datadog, and other log platforms without custom parsing.

### Separate request_time From upstream_response_time

`request_time` includes NGINX processing and client transfer time. `upstream_response_time` isolates the backend's contribution. **This distinction is critical for diagnosing whether latency originates at NGINX or the upstream.**

### Exclude Health Checks

```nginx
map $request_uri $loggable {
    /health 0;
    /ready  0;
    default 1;
}

access_log /var/log/nginx/access.log json_combined if=$loggable;
```

Health check noise obscures operational signal.

### Sensitive Data

**Never log** authorization headers, cookies, query parameters containing tokens, or request bodies. Mask or exclude at the log format level. Logs are stored, replicated, and accessible to operations teams — they are a credential exposure vector.

### Rotation

Rotate access and error logs daily. Use `logrotate` with `copytruncate` or send the `USR1` signal for zero-downtime rotation. Unrotated logs consume disk and degrade write performance as files grow.

---
[Back to Overview](./OVERVIEW.md)
