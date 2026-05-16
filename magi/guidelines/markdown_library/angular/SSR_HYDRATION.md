# Server-Side Rendering and Hydration

Angular supports SSR through `@angular/ssr` for improved load performance and SEO.

### Hydration Configuration

Use `provideClientHydration()` to reuse server-rendered DOM. Enable event replay to prevent losing user interactions during hydration. Enable incremental hydration for large apps.

```typescript
provideClientHydration(
    withEventReplay(),
    withIncrementalHydration(),
)
```

### Platform-Specific Code

- Use `isPlatformBrowser()` and `isPlatformServer()` guards.
- Avoid direct DOM access (`window`, `document`) outside browser-only blocks.
- Inject `DOCUMENT` token instead of using global `document`.
- Wrap browser-only libraries in dynamic imports gated by platform checks.

### Service Worker / PWA

Ensure the service worker registers properly without racing with hydration. Verify in shakedown that `@angular/service-worker` fetches `ngsw.json` correctly.

---
[Back to Overview](./OVERVIEW.md)
