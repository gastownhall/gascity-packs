# Style Summary

| Element | Required pattern |
|:--------|:-----------------|
| **Core** | Zenfolio is source of truth; server-side proxy for all auth/mutations; respect the Group→PhotoSet→Photo hierarchy; cache aggressively; degrade gracefully on API failure |
| **Protocol** | JSON-RPC over HTTPS exclusively; case-sensitive method names; positional params; check `error` field before `result`; `IncrementalLevel` controls response size |
| **Authentication** | Challenge-response in production; tokens expire ~24 hours; proactive refresh at 20 hours; tokens cached server-side only; credentials in secret management |
| **Keyring** | `KeyringAddKeyPlain` for password-protected galleries; accumulative keyring tokens; server-managed in headless; prompt user on access denied; verify with `KeyringGetUnlockedRealms` |
| **Data Model** | Gallery vs Collection (`Type` field); numeric IDs per object type; `LoadGroupHierarchy` for tree navigation; `LoadPhotoSetPhotos` for pagination; `TitlePhoto` for cover images |
| **Image URLs** | Smallest size for context; thumbnail for grids; large for lightbox; original for download only; responsive `srcSet`; lazy loading; preload adjacent in lightbox |
| **Access Control** | Check `AccessDescriptor` on every object; respect `SameAsContaining` inheritance; filter private from public responses; honor metadata visibility flags |
| **Mutations** | All through server-side proxy; `CreatePhotoSet` with updater objects; upload via PUT to `UploadUrl` with auth token; `UpdatePhoto` / `UpdatePhotoSet` replace full keyword arrays; delete is irreversible |
| **Search** | `SearchSetByText` for galleries; debounce queries 300-500ms; cache results 2-5 min; `GetCategories` for taxonomy with 24-hour cache |
| **Caching** | Multi-layer (proxy + React Query + HTTP headers); TTLs by content type (5min galleries, 15min popular, 24hr categories); invalidate on mutation; cache keys include method + params |
| **Error Handling** | Classify retriable vs non-retriable; exponential backoff with jitter; circuit breaker for sustained failures; user-friendly error states; never expose raw API errors |
| **Frontend Integration** | Server-side proxy (Nitro/Express); TypeScript types for all objects; custom React Query hooks; normalize gallery ID formats; lazy load + virtual scroll for large galleries |
| **E-Commerce** | Track selections by photo ID; cart bridges Zenfolio display with external checkout; `GetDownloadOriginalKey` for digital delivery after payment; selection mode with `Set`-based state |
| **Security** | Token never in client; credentials never in public env vars; strip `UploadUrl` from responses; CORS restricted to frontend origin; unauthenticated calls for public read; proxy input validation |
| **Performance** | CDN for images; responsive `srcSet`; SSR preload gallery data; parallel gallery loads; minimum `IncrementalLevel` per request |
| **Monitoring** | API call volume per method; cache hit ratio; error rate by type; frontend gallery load time; CWV tracking; Zenfolio status monitoring |
| **Testing** | Mock Zenfolio responses for unit tests; real API for scheduled integration tests; component tests with mock data; E2E for critical user flows |
| **Shakedown** | Real Zenfolio API against fixed known-good test gallery; nine validation categories; eight-step execution pattern; pass/fail-blocking/fail-nonblocking/inconclusive; four required artifacts; version-controlled fixture |
| **Defense in Depth** | Schema validation + retry/backoff + circuit breaker + local cache + DLQ + monitoring + scheduled reconciliation = seven independent layers; live API + cache + reconciliation = the Rule of Three quorum |

---

**Apply these guidelines universally to all Zenfolio API integration work.**

---
[Back to Overview](./OVERVIEW.md)
