# Framework Integration

### Auto-Detection

Netlify auto-detects and configures builds for major frameworks: Next.js, Nuxt, Astro, Remix, SvelteKit, Gatsby, Angular, Eleventy, Hugo, and others. Auto-detection identifies the framework, sets the build command, and configures the publish directory. Override any auto-detected setting in `netlify.toml`.

### Next.js

Full feature support: App Router, Pages Router, SSR, ISR, API routes, middleware, image optimization. The `@netlify/next` adapter converts:

- Server components and API routes → Netlify Functions.
- Middleware → Edge Functions.
- Static pages → CDN-served assets.

**Pin `@netlify/next` version in `package.json`** to avoid adapter version drift between builds. **Test major Next.js upgrades in a deploy preview before merging to production** — framework adapter compatibility is not guaranteed across major versions without testing.

### Vite Frameworks

For projects using Vite or Vite-powered metaframeworks (Nuxt, SvelteKit, Astro with Vite), install `@netlify/vite-plugin`. Without it, local development diverges from production behavior.

```typescript
import { defineConfig } from "vite";
import netlify from "@netlify/vite-plugin";

export default defineConfig({
  plugins: [netlify()],
});
```

The plugin brings full Netlify platform support into the local dev server: Functions, Edge Functions, Blobs, Image CDN, headers, redirects, and environment variables.

### Framework Pitfalls

Framework-specific behaviors that differ from local development must be tested in deploy previews **before** production:

- **Next.js ISR** — Netlify implements ISR through its caching infrastructure, not Next.js's native filesystem cache. Cache invalidation behaves differently — test revalidation behavior in deploy previews, not just locally.
- **SvelteKit** — `@sveltejs/adapter-netlify` generates functions and edge functions from SvelteKit routes. Ensure the adapter version matches your SvelteKit version.
- **Static site generators (Hugo, Eleventy, Jekyll)** — pin the generator version in `netlify.toml`. Hugo version mismatches are the single most common cause of build failures for Hugo sites.

---
[Back to Overview](./OVERVIEW.md)
