# Style Summary

| Element | Required Style |
|:--------|:---------------|
| **Configuration** | `netlify.toml` in repository root; secrets in UI only; pin all runtime versions |
| **Build Command** | Delegated to npm scripts; no inline Bash complexity; `ignore` command for monorepos |
| **Deploy Strategy** | Atomic deploys only; deploy previews mandatory; rollbacks tested and documented |
| **Serverless Functions** | v2 format (`Request`/`Response`); co-locate with regional databases; 10s/26s timeout |
| **Background Functions** | 15-minute async processing; `-background` suffix or `config` export; no sync response |
| **Scheduled Functions** | Cron syntax via `config` export; production-only execution; delegate long work to background |
| **Edge Functions** | Deno runtime; 50ms CPU limit; middleware pattern; geographic proximity for stateless ops |
| **Redirects** | `netlify.toml` preferred; specific rules before general; `force` used intentionally |
| **Headers** | Security baseline on all sites; `_headers` or `netlify.toml`; static assets only |
| **Caching** | Static auto-cached; dynamic opt-in via headers; SWR for latency-sensitive dynamic content |
| **Cache Control** | `Netlify-CDN-Cache-Control` for CDN; `Cache-Control` for browser; never conflate |
| **Blobs** | Key/value for unstructured data; eventual consistency default; site-level or deploy-scoped |
| **DB** | Serverless Postgres via Neon; beta; relational workloads only; cold-start aware |
| **Environment Variables** | UI for secrets; `netlify.toml` for non-sensitive; scoped by context and deploy target |
| **Image CDN** | On-demand transforms; framework image components preferred; content negotiation automatic |
| **Monorepos** | Per-site `netlify.toml`; package directory set; `ignore` filtering mandatory |
| **Framework Adapters** | Pinned versions; tested on upgrade; deploy preview verification before production |
| **Observability** | Deploy logs reviewed; function logs monitored; `Cache-Status` header for cache debugging |
| **Cost** | Usage tracked monthly; `ignore` command for build savings; Image CDN for bandwidth savings |
| **Security** | HSTS, `X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy` on all production sites |
| **Shakedown** | Real preview URL + route manifest + functions + edge + env propagation + plugin + cache headers; classify pass / fail-blocking / fail-nonblocking / inconclusive |
| **Defense in Depth** | Preview deploys + cache nuke validation + locked Node/PM + env parity + rollback drills + synthetic monitoring + DNS/cert monitoring |
| **Rule of Three** | Build success + preview-URL smoke + multi-region synthetic monitor MUST agree before declaring healthy |

---
[Back to Overview](./OVERVIEW.md)
