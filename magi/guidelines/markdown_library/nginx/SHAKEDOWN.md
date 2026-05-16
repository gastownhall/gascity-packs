# Post-Reload Shakedown

### Definition

A post-reload shakedown is the **controlled integration validation executed immediately after `nginx -s reload` or `systemctl reload nginx` completes**. Shakedown answers a question that `nginx -t` cannot: *Does the live worker pool, with the new configuration graph loaded, actually route, terminate, proxy, rate-limit, and log as declared?*

A reload that returns exit code zero proves the master accepted the new config; **it does not prove the listen sockets rebound, upstreams resolved, or TLS chains served correctly**.

### Three Distinct Phases

| Phase | Validates |
|:------|:----------|
| Preflight (`nginx -t`) | Syntax, directive existence, file presence, static correctness |
| **Shakedown** | Live probe sequence against the reloaded worker pool under controlled conditions with known-good requests |
| Testing | Sustained load, fuzzing, penetration scanning, performance benchmarking |

A passing `nginx -t` is not a passing shakedown, and a passing shakedown is not a passing test suite.

### Mandatory Triggers

Shakedown is mandatory after:

- `server_name` addition or removal.
- `listen` directive change.
- TLS certificate swap.
- Upstream block change (`server`, `max_fails`, `fail_timeout`, `keepalive`).
- `proxy_pass` target change.
- Rate limit or connection limit change.
- Location block addition or modification.
- mTLS or client-cert configuration change.
- HTTP-to-HTTPS redirect change.
- nginx binary upgrade.
- OS or OpenSSL upgrade on the host.

### Non-Triggers

- Pure comment changes.
- Whitespace-only changes.
- Log rotation configuration changes that do not alter log paths.
- Monitoring label additions that do not change routing.

Changes that touch any integration boundary require shakedown regardless of apparent size.

### Validation Categories

1. **Listener binding** — for every `listen` directive, confirm worker processes are bound on the declared address and port (`ss -ltnp | grep nginx`). **A reload that silently fails to rebind a listener leaves the previous worker serving the old configuration on that port while the new master reports success.** Missing listeners are the highest-severity shakedown failure.
2. **server_name resolution** — for every `server_name`, issue a request with the matching `Host` header and verify the expected server block responds. Include the default catch-all: a request with an unrecognized Host header must return 444 or the declared deny status.
3. **Upstream health** — for every upstream block, execute a synthetic probe that traverses the `proxy_pass` path. Verify response code, `Content-Type`, and a known-good body fragment. Passive health checks alone are insufficient.
4. **TLS negotiation** — for every HTTPS server block, run `openssl s_client -connect host:443 -servername name` and verify: protocol is TLS 1.2 or 1.3, cipher is from the approved list, certificate chain is complete, certificate matches `server_name`, expiry is beyond the alert threshold. Run on every SAN, not only on the primary name.
5. **HTTP-to-HTTPS redirect** — for every port 80 server block with a redirect rule, verify `curl -I http://host/path` returns 301 with a `Location` pointing to the expected HTTPS URL.
6. **Location routing and body forwarding** — for each location block, issue a request that must match it and confirm the response originates from the expected upstream. For `proxy_pass` locations forwarding bodies, POST a known-good payload and verify the upstream received the full body unaltered (content length, checksum, or echo-back).
7. **Rate limit and connection limit enforcement** — for every `limit_req` and `limit_conn` zone declared on a shakedown-relevant endpoint, issue a burst that exceeds the configured rate and verify the declared `limit_req_status` (429 by default) fires. **A rate limit that silently fails open is a shakedown failure.**
8. **WebSocket upgrade** — for upgrade-enabled locations, issue a request with `Upgrade: websocket` and `Connection: Upgrade` and verify the upstream completes the 101 Switching Protocols handshake.
9. **Log path writability and write activity** — confirm every declared `access_log` and `error_log` path is writable by the worker user and has received new entries matching the shakedown traffic. **A reload that silently drops log output is a shakedown failure.**
10. **mTLS** — where `ssl_verify_client` is `on` or `optional`, present a known-good client certificate and verify the upstream receives the `ssl_client_verify` and `ssl_client_s_dn` variables forwarded via `proxy_set_header`. Present an unknown certificate and verify the declared failure status (403 or 495) fires.

### Execution Discipline

- Execute against a **bounded environment** — staging nginx with production-equivalent server blocks, upstreams, and certificates.
- Shakedown in production permitted only after staging passes, and only with known-good probe requests that cannot corrupt state.
- **No optimization during shakedown** — performance anomalies are logged and deferred.

### Required Artifacts

- Reload timestamp.
- Config hash (`sha256` of `nginx -T` output).
- Probe sequence log with request/response pairs.
- Listener inventory from `ss`.
- Upstream probe results.
- TLS chain verification output.
- Log tail from `access_log` and `error_log` during the probe window.
- Classification.

**A shakedown without artifacts did not happen.**

### Result Classification

- **Pass** — every listed validation returned the expected result. Proceed to production rollout.
- **Fail-blocking** — a listener did not bind, a TLS chain is invalid, an upstream is unreachable, rate limits fail open, or mTLS accepts unknown certs. **Roll back configuration immediately.**
- **Fail-nonblocking** — a log path received entries but at an unexpected level, a non-critical header is missing, cache status is unexpected. Log to issue tracker and proceed with monitoring.
- **Inconclusive** — the probe environment could not reach an upstream due to network conditions outside nginx. Re-run shakedown with the condition resolved.

### Anti-Patterns (Forbidden)

- Treating `nginx -t` as sufficient validation.
- Running shakedown with mocked upstreams.
- Skipping shakedown after a "small" `server_name` tweak.
- Running shakedown without capturing the probe log.
- Optimizing buffer sizes or worker counts mid-shakedown.
- Reusing cached probe results from a prior reload.

### Reference Probe Sequence

```bash
#!/usr/bin/env bash
# Post-reload shakedown — run immediately after `nginx -s reload`
set -euo pipefail
HOST="api.example.com"
PROBE_LOG=".shakedown/$(date -u +%Y%m%dT%H%M%SZ).log"
mkdir -p "$(dirname "${PROBE_LOG}")"
exec > >(tee -a "${PROBE_LOG}") 2>&1

# 1. Preflight gate — must already have passed before reload
nginx -t
CONFIG_HASH="$(nginx -T 2>/dev/null | sha256sum | awk '{print $1}')"
echo "config_hash=${CONFIG_HASH}"

# 2. Listener binding
ss -ltnp | grep -E ':(80|443)\s' | grep nginx || { echo "FAIL: listeners not bound"; exit 1; }

# 3. server_name + HTTPS response
curl -sS -o /dev/null -w "server_name=%{http_code}\n" \
  --resolve "${HOST}:443:127.0.0.1" "https://${HOST}/health"

# 4. Default catch-all rejects unknown Host
code="$(curl -sS -o /dev/null -w "%{http_code}" -H "Host: spoof.invalid" "http://127.0.0.1/" || true)"
[[ "${code}" == "444" || "${code}" == "000" || "${code}" == "403" ]] || { echo "FAIL: catch-all served ${code}"; exit 1; }

# 5. HTTP->HTTPS redirect
curl -sS -o /dev/null -w "redirect=%{http_code} location=%{redirect_url}\n" \
  --resolve "${HOST}:80:127.0.0.1" "http://${HOST}/"

# 6. Upstream proxy_pass body round-trip
curl -sS -X POST --data-binary @fixtures/known-good.json \
  -H "Content-Type: application/json" \
  --resolve "${HOST}:443:127.0.0.1" "https://${HOST}/api/echo" | diff - fixtures/expected-echo.json

# 7. TLS chain + cipher
openssl s_client -connect "${HOST}:443" -servername "${HOST}" -showcerts </dev/null 2>&1 \
  | grep -E "Protocol|Cipher|Verify return code"

# 8. Rate limit enforcement
for i in $(seq 1 30); do
  curl -sS -o /dev/null -w "%{http_code}\n" \
    --resolve "${HOST}:443:127.0.0.1" "https://${HOST}/login"
done | grep -q "^429$" || { echo "FAIL: rate limit did not trigger 429"; exit 1; }

# 9. WebSocket upgrade (if applicable)
curl -sS -o /dev/null -w "ws=%{http_code}\n" \
  -H "Connection: Upgrade" -H "Upgrade: websocket" \
  -H "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==" -H "Sec-WebSocket-Version: 13" \
  --resolve "${HOST}:443:127.0.0.1" "https://${HOST}/ws"

# 10. Log activity
tail -n 20 /var/log/nginx/access.log
tail -n 20 /var/log/nginx/error.log
echo "shakedown=pass"
```

### Shakedown-Targeted Location Blocks

```nginx
# Echo upstream for body round-trip
location = /api/echo {
    limit_except POST { deny all; }
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_pass http://echo_upstream;
    proxy_read_timeout 10s;
}

# Login rate limit target
location = /login {
    limit_req zone=login_strict burst=5 nodelay;
    limit_req_status 429;
    proxy_pass http://auth_upstream;
}
```

---
[Back to Overview](./OVERVIEW.md)
