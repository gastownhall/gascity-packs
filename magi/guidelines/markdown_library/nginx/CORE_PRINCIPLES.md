# Core Principles

These guidelines define strict conventions for NGINX server block architecture, TLS hardening, reverse proxy configuration, security headers, rate limiting, performance tuning, logging, upstream resilience, and operational safety across all NGINX-fronted properties.

**Runtime:** NGINX 1.25+ (mainline) or 1.26+ (stable), OpenSSL 3.0+, Linux kernel 5.15+.

### NGINX Is the Perimeter

NGINX is the first process to touch every inbound request. Every security control, header policy, rate limit, and access restriction that can be enforced at the edge must be enforced here. Backend applications are the second line of defense, not the first. **A misconfigured NGINX exposes every upstream service simultaneously.**

### Explicit Over Implicit

NGINX inherits directives from parent contexts (`http` → `server` → `location`). This inheritance is convenient and dangerous. Every server block and location block explicitly declares the directives it requires rather than relying on inherited values that may change when a parent block is modified. **If a directive matters, state it. If it does not apply, deny it.**

### Deny by Default

The default server block returns 444 (connection close) or 403 for unmatched requests. Location blocks that serve no purpose do not exist. Access to dotfiles, backup files, version control directories, and internal paths is denied explicitly. The configuration is a whitelist of allowed behaviors, not a blacklist of known attacks.

### Test Before Reload

Every configuration change passes `nginx -t` before reload. Automated deployments gate on test success. A failed reload with `-s reload` leaves the previous working configuration in place, but a syntax error that passes `-t` but causes runtime issues (e.g., upstream DNS resolution failure) requires monitoring to catch. Test in staging with production-equivalent traffic patterns before promoting.

### Foundational Rules

- Run `nginx -t` successfully before every reload or restart. Automated pipelines must gate deployment on this check.
- Never edit NGINX configuration files directly on production servers. Configuration is version-controlled, reviewed, tested in staging, and deployed via automation.
- Use `include` directives to modularize configuration. Separate server blocks, upstream definitions, security headers, and SSL parameters into individual files under `conf.d/` or `sites-enabled/`.

---
[Back to Overview](./OVERVIEW.md)
