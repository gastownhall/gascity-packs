# Request Filtering and Access Control

NGINX processes access rules before proxying — the most efficient place to reject unwanted traffic.

### Block Dotfiles and Backups

```nginx
location ~ /\.(?!well-known) {
    deny all;
    return 404;
}

location ~* \.(bak|backup|swp|old|orig|dist|save|sql|tar\.gz|zip)$ {
    deny all;
}

location ~* /(wp-config\.php|\.env|composer\.json|package\.json)$ {
    deny all;
    return 404;
}
```

Dotfiles (`.git`, `.env`, `.htaccess`, `.DS_Store`, editor swap files) leak source code, credentials, and configuration. Backup files (`.bak`, `.swp`, `.sql`, `.tar.gz`) commonly survive deployments and contain source code or database dumps. `.well-known` is allowed for ACME challenges.

### Restrict HTTP Methods

```nginx
if ($request_method !~ ^(GET|POST|HEAD)$) {
    return 405;
}
```

Or use `limit_except` within location blocks. Restrict methods to those the application uses.

### Body Size Limits

```nginx
client_max_body_size 1m;        # default per server / location

location = /upload {
    client_max_body_size 100m;  # explicitly raised for uploads
}
```

Default is 1m. Set explicitly per location: 10m for upload endpoints, 1m for API endpoints. **Never set 0 (unlimited) globally** — enables resource exhaustion via unbounded request bodies.

### Admin Path Restriction

Restrict admin paths (`/wp-admin`, `/admin`, `/dashboard`, internal APIs) by IP, client certificate, or VPN proxy:

```nginx
location /admin/ {
    allow 10.0.0.0/8;
    allow 172.16.0.0/12;
    allow 192.168.0.0/16;
    deny  all;
    proxy_pass http://backend;
}
```

### User-Agent Filtering

```nginx
if ($http_user_agent = "") {
    return 403;
}
```

Block requests with empty User-Agent for **non-API endpoints**. Most legitimate browsers send User-Agent. Bots and scanners often omit it. Do not apply to API endpoints where programmatic clients legitimately omit it.

### Disable Server-Side Includes and Autoindex

```nginx
ssi off;
autoindex off;
```

Enable only in specific location blocks with documented justification.

---
[Back to Overview](./OVERVIEW.md)
