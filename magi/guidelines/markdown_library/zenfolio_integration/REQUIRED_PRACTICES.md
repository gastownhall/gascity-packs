# Required Practices

### Always Do

- Route all authenticated and mutating Zenfolio API calls through a server-side proxy.
- Use challenge-response authentication in production. Store credentials in secret management.
- Cache auth tokens with 20-hour TTL. Refresh proactively before expiry. **Never expose to client.**
- Include `X-Zenfolio-User-Agent` with application name and version on every API request.
- Use JSON-RPC for all new integrations. **Validate response `error` field before accessing `result`.**
- Implement server-side cache (proxy) and client-side cache (React Query / `useAsyncData`) with appropriate TTLs.
- Invalidate affected cache entries when the proxy executes any create, update, or delete operation.
- Retry transient failures with exponential backoff and jitter. Maximum 3 attempts. Cap delay at 30 seconds.
- Check `AccessDescriptor` on every object. Filter private content from public responses.
- Serve appropriate image sizes per rendering context. Thumbnails for grids, large for lightboxes, originals for downloads only.
- Lazy-load gallery photos using Intersection Observer or pagination for large galleries.
- Define TypeScript types for all Zenfolio objects. Share types between proxy and frontend.
- Wrap Zenfolio data fetching in custom hooks (`useGallery`, `usePhotos`, `useSearchGalleries`) with encapsulated caching and error handling.
- Strip `UploadUrl`, `RawUploadUrl`, `VideoUploadUrl`, and internal `AccessDescriptor` fields from proxy responses to frontend.
- Restrict proxy CORS to the frontend application origin. Block unauthorized cross-origin access.
- Track API call volume, response time, cache hit ratio, and error rate with alerting thresholds.
- Unit test proxy with mocked responses. Component test frontend with mock data. Integration test against real API on schedule.
- Run shakedown against the known-good test gallery before enabling production processing on every triggering change.
- Capture all four required shakedown artifacts (execution log, result summary, issue list, environment snapshot).

---
[Back to Overview](./OVERVIEW.md)
