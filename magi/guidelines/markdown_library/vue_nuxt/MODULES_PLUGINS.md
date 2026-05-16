# Modules and Plugins

### Nuxt Modules

Modules extend Nuxt at build time: adding auto-imports, registering plugins, modifying Vite/Webpack config, and providing runtime composables. Use official and community modules for common needs (`@nuxt/image`, `@nuxt/fonts`, `nuxt-auth-utils`, `@pinia/nuxt`). **Evaluate modules by maintenance status, bundle impact, and SSR compatibility before adoption.** Remove unused modules aggressively — each module adds build time and potentially bundle size.

### Plugins

Plugins run once during app initialization. Define in the `plugins/` directory. Plugins receive `nuxtApp` for `provide`/`inject`, hook registration, and runtime extension. Use plugins for global error handlers, analytics initialization, third-party SDK setup, and custom `provide`/`inject` bindings. Mark plugins as client-only (`.client.ts` suffix) or server-only (`.server.ts` suffix) when they use environment-specific APIs. Plugins execute in alphabetical order by default; use `dependsOn` for explicit ordering when necessary.

---
[Back to Overview](./OVERVIEW.md)
