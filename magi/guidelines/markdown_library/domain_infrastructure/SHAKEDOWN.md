# Shakedown — Post-Change Integration Validation

### Definition

A domain infrastructure shakedown is the **first controlled end-to-end validation of the full request chain — authoritative DNS → nameserver → resolver → CDN edge → origin — after any change to DNS records, certificate material, CDN rules, or origin routing**. It answers the single question: *does a real request from a real client still reach the intended origin and return an authenticated, encrypted, cacheable response?*

A shakedown is **not** routine uptime monitoring (that runs continuously regardless of changes) and it is **not** DNS syntax validation (that is preflight). It is the act of proving that a specific change did not break the chain before that change is left to run unattended.

### Shakedown vs Routine Checks

| Check | Question Answered | Frequency |
|:------|:------------------|:----------|
| Synthetic uptime monitoring | Is the endpoint serving responses right now? | Every 60s, forever |
| Certificate expiry monitoring | Is any cert within the renewal window? | Continuously, all production domains |
| DNS resolution monitoring | Do external resolvers still return the expected record? | Continuously, multiple vantage points |
| **Shakedown** | **Did the change I just made preserve the full chain?** | **Once, immediately after the change** |

### Mandatory Triggers

A shakedown is mandatory after any change that touches the request chain:

- Any DNS record change on a production zone — A, AAAA, CNAME, MX, TXT, CAA, NS.
- Any certificate issuance or renewal, including ACME automation runs that replace a live cert.
- Any CDN rule change — cache rules, page rules, workers, redirect rules, WAF rules, origin routing.
- Any origin change — origin IP, origin hostname, origin health-check path, TLS termination configuration.
- Any nameserver change at the registrar — NS delegation, DNSSEC DS record update, registrar transfer.
- Any TLS configuration change — cipher suite change, minimum TLS version change, HSTS header change, OCSP stapling toggle.
- Infrastructure change on the origin: new base image, new load balancer, new reverse proxy, new Kubernetes ingress.
- After DNSSEC key rollover (ZSK or KSK), even when automated.

### Non-Triggers

A shakedown is **not** required for:

- Cache purges against already-validated cache rules.
- Adding a monitoring probe target to the observability platform.
- Internal documentation updates that reference a domain without changing it.
- Routine TTL extensions on stable records that have been steady-state for 30+ days.

### Validation Categories

Every shakedown must exercise these categories. Each maps to a real incident class.

1. **Authoritative resolution from multiple vantage points** — query the record via `dig +short @8.8.8.8`, `@1.1.1.1`, `@9.9.9.9`, `@208.67.222.222`, and at least one regional resolver; all responses must match the expected value.
2. **TLS certificate chain validation with real OCSP/CRL check** — confirm leaf chains to a trusted root, intermediate(s) served by origin or stapled by CDN, OCSP stapling returns "good", chain hostname matches the request target.
3. **CDN rule engine hit path** — request a known test URL designed to trigger every rule (cache, transform, redirect, WAF) and verify each fired via CDN trace headers (`CF-Cache-Status`, `X-Cache`, `X-Edge-Location`).
4. **Origin reachability and health-check path** — request the configured origin health-check path directly (bypassing CDN if the origin firewall allows) and confirm 200 with expected body.
5. **HTTP → HTTPS redirect enforcement** — issue a plaintext HTTP request and confirm 301/308 to HTTPS with no cookie or body leakage on the plaintext response.
6. **HSTS preload header presence** — confirm `Strict-Transport-Security` is present with `max-age ≥ 31536000`, `includeSubDomains` if applicable, and `preload` if on the HSTS preload list.
7. **Alternate origin failover** — disable the primary via CDN console (or simulate unhealthy via health-check manipulation); confirm traffic shifts to alternate within the failover window; re-enable primary and confirm recovery.
8. **DNSSEC chain validation** — `dig +dnssec +cd` against the record; confirm the AD (Authenticated Data) flag is returned by validating resolvers; verify via `dnsviz.net` or Verisign DNSSEC Debugger.

### Execution Principles

- **Conservative inputs** — a small fixed set of known test URLs with known expected responses; no fuzz testing, no adversarial inputs, no edge cases.
- **Progressive stress** — start with one URL from one vantage point, then expand to multiple vantage points, then expand to additional URLs; stop at the first failure and diagnose before advancing.
- **Controlled environment** — shakedown against the real production DNS, real certificate, real CDN configuration, and real origin; synthetic environments with different record sets defeat the purpose.
- **Observable execution** — full request and response headers captured, TLS handshake logged (`openssl s_client -connect -servername`), DNS query transcripts retained, CDN trace headers preserved.
- **Known-good URLs** — a fixed shakedown URL corpus maintained alongside the zone inventory; each URL has a known expected status, headers, and body hash.
- **No optimization during shakedown** — performance anomalies (slow TLS handshake, slow origin response) are logged and deferred to the performance team.

### Post-Change Shakedown Sequence

| Step | Action |
|:----:|:-------|
| 1 | Preflight: confirm the change was published — zone serial incremented, cert deployed to CDN and origin, CDN rule list reflects the change, origin health-check reports healthy |
| 2 | Authoritative DNS check: `dig +short @ns1.provider.com <record>` and confirm expected value from every authoritative nameserver in the NS set |
| 3 | Propagation check: `dig +short @8.8.8.8`, `@1.1.1.1`, `@9.9.9.9`, `@208.67.222.222 <record>`; confirm all return expected value. Stale responses mean wait for the old TTL to expire and re-query |
| 4 | DNSSEC validation: `dig +dnssec +cd @1.1.1.1 <record>`; confirm AD flag is set; confirm DS at registrar matches KSK at authoritative server |
| 5 | TLS chain validation: `openssl s_client -connect <host>:443 -servername <host> -showcerts -status`; confirm leaf, intermediate chain, hostname match, OCSP stapling status "good"; `openssl verify` against system root store |
| 6 | HTTP → HTTPS redirect: `curl -I http://<host>/`; confirm 301/308 to HTTPS, no `Set-Cookie` on plaintext response |
| 7 | HSTS header: `curl -I https://<host>/`; confirm `Strict-Transport-Security` with expected max-age, includeSubDomains, preload |
| 8 | CDN hit path: request a known test URL; capture `CF-Cache-Status`, `Age`, `X-Cache`, trace headers; confirm expected rule fired |
| 9 | Origin reachability: from a permitted vantage point (CDN shield IP or origin admin network), request origin health-check path and confirm 200 with expected body |
| 10 | Alternate origin failover (if configured): disable primary via CDN health-check override; confirm shift to alternate; capture trace; re-enable primary; confirm recovery |
| 11 | Record artifacts — dig transcripts, openssl output, curl header dumps, CDN trace headers, environment snapshot (zone serial, cert thumbprint and expiry, CDN rule set ID/hash, origin version) — tag with change ticket ID |
| 12 | Classify the result: pass, fail-blocking, fail-nonblocking, or inconclusive |

### New-Certificate Shakedown Sequence

Certificates are the most frequent source of post-change outages — expired intermediates, missing chain, wrong hostname, SAN mismatch. Run this sequence after any issuance or renewal:

| Step | Action |
|:----:|:-------|
| 1 | Confirm the new certificate is deployed to every edge or origin that terminates TLS for the domain |
| 2 | `openssl s_client -connect <host>:443 -servername <host> -showcerts` from at least three geographic vantage points; confirm the same leaf fingerprint everywhere |
| 3 | Validate the full chain: leaf → intermediate(s) → trusted root; confirm no "unable to get local issuer certificate" errors |
| 4 | Confirm subject and SAN list include every hostname the domain serves — apex, www, and any subdomains covered |
| 5 | Confirm OCSP stapling returns "good" (`openssl s_client -status`); if CDN does not staple, confirm the OCSP responder URL is reachable and returns "good" for the serial |
| 6 | Monitor CT logs (crt.sh, Cert Spotter) within 24h to confirm publication and detect any unauthorized issuance in parallel |
| 7 | Capture artifacts: openssl output, CT log entry links, certificate fingerprint and expiry, deployment targets confirmed |

### Result Classification

Every shakedown run produces an explicit classification and a complete artifact set. Silent success is prohibited.

- **pass** — all checks return expected values from every vantage point; the change is cleared.
- **fail-blocking** — any DNS mismatch, TLS chain error, missing HSTS header, origin unreachable, or CDN rule not firing. Roll back, fix root cause, re-run from step 1.
- **fail-nonblocking** — observed anomaly that does not break the chain (e.g., slower TLS handshake than baseline) but warrants a ticket with full diagnostic context.
- **inconclusive** — propagation not yet complete, vantage point returned SERVFAIL transiently, OCSP responder unreachable. Wait and re-run the affected step.

### Required Artifacts

Every shakedown produces four artifacts retained with the change ticket:

- **Execution log** — timestamped transcript of every dig, openssl, and curl command with full output.
- **Result summary** — per-category pass/fail classification with explicit verdict.
- **Issue list** — every anomaly, classified blocking/non-blocking, with reproduction context.
- **Environment snapshot** — zone serial, nameserver list, certificate thumbprint and expiry, CDN rule set version, origin version, DNSSEC key IDs.

### Anti-Patterns (Forbidden)

- Skipping shakedown after "just a TTL change" — TTL changes have shifted cached values and caused routing anomalies during failover.
- Running shakedown from a single vantage point — DNS inconsistencies between resolvers are common and invisible from one location.
- Trusting the CDN dashboard's "healthy" status instead of issuing real requests — dashboards cache stale health state.
- Checking TLS via browser instead of `openssl s_client` — browsers cache validation results and hide chain errors behind "trusted".
- Treating shakedown as a comprehensive test suite — shakedown is a fixed small corpus, not assertion-heavy coverage.
- Optimizing CDN rules or origin code during shakedown — note it, log it, move on; optimization introduces new changes that themselves need validation.
- Failing to capture artifacts because "the run passed" — a shakedown without artifacts is a shakedown that never happened.

---
[Back to Overview](./OVERVIEW.md)
