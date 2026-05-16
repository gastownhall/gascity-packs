# Headless Frontend Integration

Headless frontends (React, Nuxt, Next.js) consume the Zenfolio API through a server-side proxy. **The frontend interacts with the proxy, not with Zenfolio directly, for all authenticated or sensitive operations.**

### Proxy Layer

| Stack | Implementation |
|:------|:---------------|
| Nuxt 3 | Nitro server routes (`server/api/zenfolio/`) |
| Next.js | API routes or Route Handlers |
| Standalone React | Express/Fastify backend or serverless functions |

The proxy:

- Authenticates to Zenfolio.
- Caches responses.
- Transforms data shapes for frontend consumption.
- **Strips sensitive fields** (`UploadUrl`, `AccessDescriptor` internals, owner metadata) from responses sent to the client.

### TypeScript Types

Define TypeScript types for all Zenfolio API objects:

- `Gallery` (PhotoSet).
- `Photo`.
- `PhotoDetail`.
- `Group`.
- `AccessDescriptor`.
- `GalleryFilters`.
- API response wrappers.

**Share types between the proxy and the frontend** via a shared types directory.

### Custom Hooks

Wrap Zenfolio-specific fetching in custom hooks:

- `useGallery(galleryId)`
- `usePhotos(galleryId, page)`
- `useGalleryWithPhotos(galleryId)`
- `useSearchGalleries(query)`

These hooks encapsulate cache keys, stale times, error handling, and loading states.

### Gallery ID Normalization

Gallery IDs may appear as:

- Bare numeric strings (`993412712`).
- Prefixed strings (`f993412712`, `p1076461859`).
- Full URLs (`https://phloxphotos.com/f993412712`).

The **proxy's ID parsing layer normalizes all formats to the bare numeric ID** before calling the Zenfolio API. The `f` prefix typically denotes a **gallery** (folder); `p` denotes a **photo**. Parse and validate before API submission.

### Lazy Loading

For photo grids:

- Use **Intersection Observer** to load images only when they scroll into view.
- For large galleries (500+ photos), implement **virtual scrolling** or infinite scroll pagination fetching 50-100 photos per page via `LoadPhotoSetPhotos` with `startingIndex` and `numberOfPhotos`.
- Display a skeleton grid during loading.

### Lightbox

- **Preload adjacent photos**. When viewing photo N, preload photos N-1 and N+1 as medium or large images. Enables instant navigation without visible loading delay.
- **Keyboard navigation** (`ArrowLeft`, `ArrowRight`, `Escape`) is mandatory for accessibility.
- **Touch swipe support** is mandatory for mobile.

---
[Back to Overview](./OVERVIEW.md)
