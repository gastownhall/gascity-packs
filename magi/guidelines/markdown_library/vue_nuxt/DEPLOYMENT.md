# Deployment

### Deployment Presets

Nitro auto-detects the deployment target or accepts an explicit preset via `NITRO_PRESET` or `nuxt.config.ts` `nitro.preset`.

| Preset | Use |
|:-------|:----|
| `node-server` | Traditional Node.js hosting |
| `vercel` / `netlify` / `cloudflare-pages` / `azure` | Platform-specific optimizations |
| `static` | Fully pre-rendered sites |

The preset determines the output format, server entry point, and platform-specific adapters. **Test builds with the target preset in CI before deployment.**

### Production Configuration

Production builds (`nuxt build`) inline environment-agnostic configuration. Environment-specific values come from runtime config via environment variables. **Verify all required environment variables exist at application startup — fail fast with explicit error messages** rather than serving broken pages because an API URL is undefined. Health check endpoints (`server/api/health.get.ts`) verify connectivity to downstream services and return structured status for monitoring.

---
[Back to Overview](./OVERVIEW.md)
