# Image CDN and Asset Optimization

### Netlify Image CDN

Transforms images on demand via URL parameters. Transformations run at the CDN edge and cache results. **No build-time processing required.** Content negotiation automatically selects the most efficient format when `fm` is omitted — modern browsers receive AVIF or WebP; legacy browsers receive JPEG/PNG.

```text
/.netlify/images?url=/images/hero.jpg&w=800&q=75&fm=webp
```

| Param | Purpose |
|:------|:--------|
| `w` | Width |
| `h` | Height |
| `q` | Quality (1–100) |
| `fm` | Format: `webp`, `avif`, `jpg`, `png` |
| `fit` | `cover`, `contain`, `fill` |

Most frameworks on Netlify (Next.js, Nuxt, Astro, Remix) integrate with Image CDN automatically through their image components and Netlify adapters. **Use framework-native image components rather than constructing Image CDN URLs manually.**

### Asset Optimization (Post-Processing)

Netlify offers optional post-processing for CSS, JavaScript, and image assets. Enable cautiously — minification and bundling at the platform level can conflict with build-tool output that is already optimized.

Modern build tools (Vite, esbuild, webpack) produce optimized output by default. Double-optimization wastes build time and occasionally introduces bugs through incompatible minification passes. **Disable Netlify's asset optimization when your build tool already handles minification.** Enable it only for legacy projects without a build-time optimization step.

---
[Back to Overview](./OVERVIEW.md)
