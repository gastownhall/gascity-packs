# Prohibited Practices

### Never Do

- Edit NGINX config files directly on production hosts. All changes deploy via version control and CI/CD.
- Reload NGINX without running `nginx -t`. Syntax errors take the server offline.
- Enable TLS 1.0 or 1.1. Both are deprecated per RFC 8996 and vulnerable to known attacks.
- Leave `server_tokens on`. NGINX version disclosure aids targeted exploitation.
- Omit a default catch-all server block. Unmatched requests reach the first server block in configuration order.
- Serve application content over HTTP (port 80). All content serves over HTTPS. Port 80 redirects to 443 exclusively.
- Allow access to dotfiles (`.git`, `.env`, `.htaccess`). These leak credentials, source code, internal configuration.
- Set `default_type text/html`. Unknown file types render as HTML, enabling XSS via uploaded content.
- Proxy to upstreams without setting `Host`, `X-Real-IP`, `X-Forwarded-For`, and `X-Forwarded-Proto` headers.
- Set `client_max_body_size 0` globally. Enables resource exhaustion via unbounded request bodies.
- Use `if` directives for general conditional logic in location blocks. Use `map` for variable-based conditions.
- Allow unlimited `proxy_next_upstream_tries`. Amplifies load on failing upstream pools.
- Log authorization headers, cookies, or tokens in access logs. Logs become credential stores.
- Use self-signed certificates in production. Use ACME/Let's Encrypt or managed certificates.
- Allow PHP execution in upload directories. Primary webshell attack vector.
- Treat `nginx -t` as sufficient validation. Run a §26 shakedown after every config change.

---
[Back to Overview](./OVERVIEW.md)
