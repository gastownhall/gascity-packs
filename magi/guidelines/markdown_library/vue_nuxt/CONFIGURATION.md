# Configuration and Runtime Config

### nuxt.config.ts

`nuxt.config.ts` is the central configuration file. **Keep it declarative and focused.** Complex logic does not belong here — use modules and plugins. Configure rendering mode, modules, runtime config, route rules, build options, and Vite/Webpack overrides. Avoid deeply nested or overly clever configuration. **The config file must be readable by any team member in under 60 seconds.**

### Runtime Config

Use `runtimeConfig` for values that vary between environments (API URLs, feature flags, service endpoints). Private keys live in `runtimeConfig` (server-only). Public keys live in `runtimeConfig.public` (available on both server and client). Access via `useRuntimeConfig()` in composables, components, and server routes. Environment variables override runtime config: `NUXT_PUBLIC_API_URL` overrides `runtimeConfig.public.apiUrl`.

**API keys, database credentials, signing secrets, and any sensitive value must be in `runtimeConfig` (private), never in `runtimeConfig.public`.** Public config is visible in the browser's page source.

### Environment Management

Use `.env` files for local development. Use environment variables (set by CI/CD, container orchestration, or hosting platform) for staging and production. **Do not commit `.env` files to version control.** Document all required environment variable names and descriptions. Nuxt reads `.env` automatically in development. **In production, environment variables must be set in the runtime environment** — `.env` files are not read in production builds by default.

---
[Back to Overview](./OVERVIEW.md)
