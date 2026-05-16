# Testing

| Layer | Strategy |
|:------|:---------|
| **Proxy unit tests** | Mocked Zenfolio API responses. Verify successful response handling, error responses, auth token refresh, cache hit/miss, response transformation. **Do not call the real Zenfolio API in unit tests** |
| **Proxy integration tests** | Real Zenfolio API with known gallery IDs in test/staging. Verify `LoadPhotoSet` returns expected fields, search returns results for known queries, auth flow produces a valid token. Run on a **schedule (daily)** rather than on every commit to avoid unnecessary API load |
| **Frontend component tests** | Mock data matching the TypeScript types. Verify rendering of loading states, error states, empty galleries, single-photo galleries, large galleries (100+ photos). Test keyboard navigation in the lightbox. Test responsive layout at mobile/tablet/desktop. Test photo selection mode add/remove/clear behavior |
| **E2E** | Critical user flow: browse galleries → select gallery → view photo grid → open lightbox → navigate photos → add to cart → proceed to checkout. Run against a production-like environment with real Zenfolio gallery IDs |

---
[Back to Overview](./OVERVIEW.md)
