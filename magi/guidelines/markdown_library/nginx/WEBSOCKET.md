# WebSocket Proxying

```nginx
map $http_upgrade $connection_upgrade {
    default upgrade;
    ''      '';
}

location /ws {
    proxy_pass http://websocket_upstream;
    proxy_http_version 1.1;
    proxy_set_header Upgrade    $http_upgrade;
    proxy_set_header Connection $connection_upgrade;
    proxy_read_timeout 300s;
}
```

| Constraint | Detail |
|:-----------|:-------|
| `Upgrade` and `Connection` headers | Required — without them, NGINX does not forward the protocol upgrade and the WebSocket handshake fails |
| `proxy_read_timeout` | Maximum expected idle time (300–3600s depending on application heartbeat); default 60s closes idle WebSockets prematurely |
| `map $http_upgrade $connection_upgrade` | Conditionally sets the `Connection` header so non-WebSocket requests to the same upstream are unaffected |

---
[Back to Overview](./OVERVIEW.md)
