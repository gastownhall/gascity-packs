# Defense in Depth

Multiple, independent layers protect NGINX configuration and runtime from a single failure. This is failure-mode defense in depth (not security defense in depth): every step has a fallback, every assumption is independently verified, every action is reversible. If any one layer breaks, silently degrades, or returns the wrong answer, at least two other layers MUST still catch the failure before it reaches production.

**Intent:** No single check, person, tool, or system is trusted to be the only safeguard.

### Independent Layers of Defense

1. **`nginx -t` config test** — MUST run before every reload; reloads with broken config are forbidden.
2. **Upstream health checks** — Active health checks (or NGINX Plus / OpenResty equivalents) MUST monitor every upstream. "Up" is a state, not an assumption.
3. **Multiple workers and instances** — `worker_processes auto` + multiple nginx instances behind a TCP load balancer. A single nginx is a single point of failure.
4. **TLS renewal monitoring** — Certificates MUST renew automatically (cert-manager / certbot) and MUST be monitored for expiry independently of the renewal job.
5. **Rate limiting and circuit breakers** — `limit_req` and `limit_conn` MUST protect upstreams from cascading failures.
6. **Structured access and error logs** — Logs MUST be shipped to a central aggregator with alerts on 5xx spikes.
7. **Blue/green or canary reload** — Config changes MUST be staged on a canary instance before fleet-wide reload.

### The Rule of Three — Majority Wins

One signal is unverifiable. Two signals disagree with no tiebreaker. Three independent signals always produce a majority.

- **One is a claim** — `nginx -t` passing is one signal; it tells you syntax is valid, NOT that the runtime upstream is healthy.
- **Two is a tie** — Config valid + access log clean but error log showing 502s is the upstream dissent; the error log wins.
- **Three is a quorum** — `nginx -t` + active upstream health checks + production 5xx-rate alert form the triple. All three MUST agree before declaring a config push successful.

Example: a `nginx -t`-clean change that points at the wrong upstream port produces 502s in production; the error log and active health check are the two voters that override the syntactic green light.

---
[Back to Overview](./OVERVIEW.md)
