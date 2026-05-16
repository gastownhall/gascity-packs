# Rate Limiting and API Usage

Zenfolio does not publish explicit rate limits, **but excessive API usage will result in throttling or temporary blocks**. The caching and proxy architecture is designed to minimize API calls.

### Self-Imposed Rate Limit

**Implement client-side rate limiting in the server-side proxy.** Limit outbound Zenfolio API calls to a sustainable rate (e.g., **10 requests/second**). **Queue excess requests.** This self-imposed limit prevents accidental API abuse from high-traffic events (gallery launch, social media viral share) and ensures predictable behavior under load.

### Monitoring

- **Log each Zenfolio API call** with method name, response time, cache hit/miss, HTTP status.
- **Alert when call volume exceeds expected baselines.** A sudden spike indicates a cache failure, a retry loop, or unexpected traffic.
- **Diagnose and remediate before Zenfolio throttles the integration.**

### Batching

Batch related requests where possible:

- `LoadPhotoSet` with `includePhotos=true` is **one request** instead of `LoadPhotoSet` + `LoadPhotoSetPhotos` (two requests).
- `useMultipleGalleries` hook can parallelize gallery loads, but each gallery is still a separate API call.
- For initial page loads requiring multiple galleries, **preload the group hierarchy** and extract gallery metadata from it rather than loading each gallery individually.

---
[Back to Overview](./OVERVIEW.md)
