# Required Practices

### Always Do

- Run `nginx -t` before every reload. Gate CI/CD deployments on test success.
- Track all NGINX configuration in version control with review and audit trail.
- Define a `default_server` block returning 444 for unmatched hosts.
- Serve all content over HTTPS. Redirect HTTP to HTTPS with 301.
- Enable only TLS 1.2 and TLS 1.3 with strong cipher suites.
- Include the full certificate chain (server + intermediates) in `ssl_certificate`.
- Automate certificate renewal with alerting on expiry.
- Set HSTS, `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, and `server_tokens off` on all responses.
- Set `Host`, `X-Real-IP`, `X-Forwarded-For`, `X-Forwarded-Proto` on all `proxy_pass` locations.
- Deny access to dotfiles, backup files, and configuration files.
- Apply strict rate limits on authentication endpoints.
- Set `client_max_body_size` per location based on expected content.
- Use JSON access log format with upstream timing for log aggregation.
- Define `/health` (NGINX-only) and `/ready` (upstream-dependent) health check endpoints restricted to internal networks.
- Export `stub_status` metrics to monitoring with alerting on error rates, latency, and connection limits.
- Run a §26 shakedown after every reload that touches integration boundaries.

---
[Back to Overview](./OVERVIEW.md)
