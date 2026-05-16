# Environment Variables and Secrets

### Declaration and Scoping

Declare environment variables in the **Netlify UI for secrets** and sensitive configuration. Declare non-sensitive structural variables in `netlify.toml`. The UI provides scoping controls unavailable in the config file.

Scope variables to the minimum required context:

| Scope | Availability |
|:------|:-------------|
| Builds | Build step only |
| Functions | Function runtime only; not during build |
| Runtime | Post-processing only |
| Deploy context targeting | Staging API key must not be available in production context, and vice versa |

**Forbidden:**

- Committing secrets, API keys, or tokens to `netlify.toml`.
- Using the same API key across production and preview contexts.

### Reserved Variables

Netlify exposes read-only variables during builds. Use these in build scripts and ignore commands without redeclaring them.

| Variable | Meaning |
|:---------|:--------|
| `COMMIT_REF` | Current commit SHA |
| `BRANCH` | Current branch name |
| `CONTEXT` | Deploy context (`production`, `deploy-preview`, `branch-deploy`) |
| `DEPLOY_URL` | URL of the current deploy |
| `DEPLOY_PRIME_URL` | Primary URL of the current deploy |
| `URL` | Site primary URL |
| `REPOSITORY_URL` | Repository URL |
| `CACHED_COMMIT_REF` | Last successfully deployed commit SHA |
| `PULL_REQUEST` | `true` if the build is from a pull request |

`CI=true` is set by default — some tools behave differently in CI mode (treating warnings as errors, disabling interactive prompts). Override with `CI=''` in the build command if this causes issues.

### Client-Side Variable Exposure

Environment variables are not embedded in static site output automatically. To expose to client-side code, use your framework's convention (`NEXT_PUBLIC_*` for Next.js, `VITE_*` for Vite) or inject via snippet injection during post-processing.

**Never expose secrets to client-side code** — server-side variables accessed via functions remain hidden from the browser; client-side variables compile into the JavaScript bundle and are visible to anyone inspecting source.

---
[Back to Overview](./OVERVIEW.md)
