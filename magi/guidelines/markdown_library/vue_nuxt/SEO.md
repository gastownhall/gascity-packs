# SEO and Head Management

### Head Management

Use `useHead()` or `useSeoMeta()` composables for dynamic head tags. `useSeoMeta` provides a flat, typed API for common meta tags (`title`, `description`, `ogTitle`, `ogImage`, `twitterCard`). Define default head tags in `nuxt.config.ts` `app.head`. Page-level overrides merge with defaults. Use `useServerSeoMeta()` for tags that only need server rendering (social previews, crawlers) to reduce client bundle size. Title templates defined in layouts provide consistent title formatting across pages.

### Structured Data

Add JSON-LD structured data via `useHead` with script tags of type `application/ld+json`. Schema.org markup improves search result presentation. **Generate structured data from the same data sources that populate the page content** to ensure consistency. Validate structured data with the Rich Results Test during development.

---
[Back to Overview](./OVERVIEW.md)
