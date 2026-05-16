# Connection Limiting

Connection limits (`limit_conn`) complement rate limits by restricting concurrent connections per key. **Mitigates slowloris and resource exhaustion** from clients that open connections without sending requests.

```nginx
http {
    limit_conn_zone $binary_remote_addr zone=conn_limit:10m;
}

server {
    limit_conn        conn_limit 50;
    limit_conn_status 429;
}
```

Tune the limit based on expected legitimate concurrency per client.

---
[Back to Overview](./OVERVIEW.md)
