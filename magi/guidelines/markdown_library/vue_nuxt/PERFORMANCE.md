# Performance

### Bundle Optimization

| Target | Limit |
|:-------|:------|
| Initial JavaScript (gzipped) for content-focused pages | Under 200 KB |

Monitor bundle size with `nuxt analyze`. Use lazy components for non-critical UI. Import only what is needed from utility libraries (tree-shaking). Avoid importing entire libraries when only a single function is used. Use dynamic `import()` for heavy dependencies loaded on interaction. Configure Vite's `build.rollupOptions.output.manualChunks` for strategic code splitting when auto-splitting is insufficient.

### Image Optimization

Use Nuxt Image (`@nuxt/image` module) for automatic optimization, responsive sizing, and lazy loading. Configure image providers for CDN-based optimization (Cloudflare, imgix, Vercel). Use the `<NuxtImg>` and `<NuxtPicture>` components instead of raw `<img>` tags. Specify `width` and `height` attributes to prevent layout shift. Use `loading="lazy"` for below-the-fold images and `loading="eager"` with `fetchpriority="high"` for above-the-fold hero images.

### Core Web Vitals

| Metric | Target |
|:-------|:------:|
| LCP | Under 2.5s |
| INP | Under 200ms |
| CLS | Under 0.1 |

SSR provides strong LCP by default. Preserve it by minimizing client-side JavaScript that blocks interactivity. Avoid layout shifts from lazy-loaded content without dimensions, font swaps without `size-adjust`, and client-side-only rendering of visible content. Monitor vitals in production via Real User Monitoring (`web-vitals` library, analytics integration, or observability platform).

### Payload Optimization

Nuxt serializes all `useAsyncData`, `useFetch`, and `useState` values into the page payload for hydration. **Large payloads increase page weight and hydration time.** Use the `transform` option on `useFetch` to strip unnecessary fields before serialization. Avoid fetching entire collections when the page only displays a subset. Paginate server-side. Audit payload size in the browser's view-source: search for `__NUXT_DATA__` and measure its size.

---
[Back to Overview](./OVERVIEW.md)
