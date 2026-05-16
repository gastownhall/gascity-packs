# Server Block Architecture

Server blocks (virtual hosts) route requests based on the `Host` header and listener configuration. A disciplined server block architecture prevents request misrouting, certificate mismatches, and default-handler exposure.

### Default Catch-All

Define a catch-all server block on ports 80 and 443 with `default_server`. Return 444 for unrecognized Host headers — this prevents requests with spoofed or missing Host headers from reaching application server blocks.

```nginx
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name _;
    return 444;
}

server {
    listen 443 ssl default_server;
    listen [::]:443 ssl default_server;
    server_name _;
    ssl_certificate     /etc/nginx/ssl/default.crt;
    ssl_certificate_key /etc/nginx/ssl/default.key;
    return 444;
}
```

### Application Server Blocks

- Every application server block specifies `server_name` with the **exact FQDN(s)** it serves. Wildcard `server_name` (`*.example.com`) is acceptable only for documented wildcard certificate deployments. Bare `server_name ""` or underscore (`_`) is reserved for the default catch-all only.
- One server block per logical service. Do not combine unrelated domains in a single server block even if they share an upstream — coupling configuration lifecycle is a defect.
- Place server blocks in individual files (`conf.d/example.com.conf`) rather than in a monolithic `nginx.conf`. Enables per-service deployment, review, and rollback.

### HTTP-to-HTTPS Redirect

Port 80 server blocks redirect to HTTPS exclusively. **No application content serves over HTTP.** Use `return 301`, not `rewrite`:

```nginx
server {
    listen 80;
    listen [::]:80;
    server_name example.com www.example.com;
    return 301 https://$host$request_uri;
}
```

---
[Back to Overview](./OVERVIEW.md)
