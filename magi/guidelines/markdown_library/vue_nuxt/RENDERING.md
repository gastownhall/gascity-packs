# Nuxt 3 Rendering Strategies

### Universal (SSR) Rendering

Default rendering mode. The server generates full HTML on each request, sends it to the client, and Vue hydrates the static markup into an interactive application. SSR provides optimal first contentful paint, SEO indexability, and social media preview support. **Every page must render meaningful content on the server.** Pages that render empty shells server-side and fetch all data client-side are SPA behavior masquerading as SSR — they get the cost of SSR (server compute) without the benefit (fast first paint, SEO).

### Static Site Generation (SSG)

Pre-render pages at build time using `nuxt generate`. Appropriate for content that changes infrequently: marketing pages, documentation, blog posts. SSG pages serve from CDN without server compute. Configure pre-rendered routes via `nuxt.config.ts` `routeRules` or the `prerender.routes` option. Dynamic routes require explicit enumeration via `prerender.routes` or a crawl strategy. SSG content is stale until the next build — use ISR for content that needs periodic freshness without full rebuilds.

### Incremental Static Regeneration (ISR)

ISR combines SSG's CDN performance with SSR's content freshness. Configure per-route via `routeRules` with `swr` (stale-while-revalidate) or `isr` options. The first request after cache expiry serves the stale page while regenerating in the background; subsequent requests receive the fresh page. Set TTL based on content update frequency: minutes for product listings, hours for blog posts, days for legal pages. ISR requires a Node.js server or compatible hosting (Vercel, Netlify, Cloudflare) for background regeneration.

**Define `routeRules` from most specific to least specific.** Rules merge, with more specific paths overriding general patterns. A rule on `/blog/**` applies to all blog routes; a rule on `/blog/featured` overrides it for that specific path.

### Hybrid Rendering

Nuxt 3 supports per-route rendering configuration via `routeRules` in `nuxt.config.ts`. Mix SSR, SSG, ISR, and SPA modes across routes within a single application. Marketing pages pre-render as SSG. Product pages use ISR with a 5-minute TTL. User dashboard routes render as SPA (`ssr: false`). API routes handle server-side logic via Nitro. **This granularity eliminates the forced tradeoff between performance and dynamism.**

### SPA Mode

Disable SSR per-route (`routeRules: { '/dashboard/**': { ssr: false } }`) or globally (`ssr: false` in `nuxt.config.ts`) for authenticated dashboards or interactive applications where SEO is irrelevant. SPA mode skips server rendering entirely — the client receives an empty shell and Vue mounts from scratch. No hydration mismatches are possible in SPA mode, but no server-rendered content exists for crawlers or users with slow connections. **Use sparingly and only with explicit justification.**

---
[Back to Overview](./OVERVIEW.md)
