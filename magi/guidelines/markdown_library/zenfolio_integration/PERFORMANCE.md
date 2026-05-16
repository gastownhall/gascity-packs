# Performance Optimization

Performance optimization spans **API call efficiency, image delivery, and frontend rendering**.

### CDN

Zenfolio serves images from its own CDN infrastructure. If the proxy layer re-serves images, configure a CDN (Cloudflare, CloudFront) in front of the proxy's image endpoints. **For direct Zenfolio image URLs rendered in the frontend, the browser fetches from Zenfolio's CDN directly — no proxy intermediary is needed for image bytes.**

### Responsive srcSet

Generate `srcSet` values from the Photo object's multiple size URLs:

| Viewport | URL |
|:---------|:----|
| Small | `thumbnailUrl` |
| Medium | `mediumUrl` |
| Desktop | `largeUrl` |

The browser selects the appropriate image size based on viewport and device pixel ratio, **reducing bandwidth on mobile devices**.

### SSR Preload

Preload gallery data during SSR for Nuxt/Next.js applications:

- **Nuxt:** `useAsyncData`.
- **Next.js:** `getServerSideProps`.

The gallery renders immediately on first paint without a client-side loading spinner. **React Query hydrates from the SSR-provided data, avoiding a duplicate fetch on the client.**

### Parallel Gallery Loads

For gallery browsers displaying many galleries (20+), load gallery metadata in parallel using `Promise.allSettled` or the `useMultipleGalleries` hook. **Parallel loading reduces total load time from serial (N × latency) to parallel (1 × latency + processing).** Handle individual gallery load failures gracefully — display the galleries that loaded successfully and show error states for failed ones.

---
[Back to Overview](./OVERVIEW.md)
