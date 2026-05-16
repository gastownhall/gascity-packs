# Shakedown — Integration Validation

A Zenfolio shakedown is a **controlled, end-to-end validation run against a fixed, known-good test gallery on a real Zenfolio account before production gallery processing is enabled** on any modified integration path. The shakedown proves that authentication, API navigation, asset retrieval, metadata propagation, rate-limit behavior, error recovery, and downstream sync all execute correctly together under real Zenfolio API conditions. **It is not a replacement for unit tests, not a load test, and not an exhaustive traversal of the live gallery catalog.**

**A passing shakedown against the designated test gallery is a hard prerequisite for enabling or re-enabling production gallery processing.** Production processing without a green shakedown is **a release blocker and a policy violation**.

### Preflight vs Shakedown vs Testing

| Phase | What it validates |
|:------|:------------------|
| **Preflight** | Static prerequisites — Zenfolio credentials in secret store, `X-Zenfolio-User-Agent` configured, TLS trust store current, proxy cache layer reachable, DNS for `api.zenfolio.com` resolves. **Answers: "ready to attempt Zenfolio calls"** |
| **Shakedown** | Full integration path against the real Zenfolio API with the known-good test gallery — auth, hierarchy traversal, asset download, metadata check, downstream propagation. **Answers: "executes correctly end-to-end against a real gallery"** |
| **Testing** | Behavioral correctness at scale — property-based tests over photoset shapes, concurrency tests on the proxy cache, regression suites for URL parsing. **Answers: "behaviorally correct across the input space"** |

### Mandatory Triggers

Shakedown is mandatory before production gallery processing is enabled after:

- First-ever deployment of a Zenfolio integration.
- Any change to authentication flow (`AuthenticatePlain` to challenge-response, token cache logic, token refresh scheduling).
- Any change to the server-side proxy layer (Nitro routes, Express routes, serverless functions that speak to Zenfolio).
- Any change to `LoadGroupHierarchy`, `LoadPhotoSet`, `LoadPhotoSetPhotos`, or `LoadPhoto` call construction, parameter ordering, or `IncrementalLevel` selection.
- Any change to image URL construction, size selection, or URL parsing (`f`-prefix / `p`-prefix normalization).
- Any change to keyring handling for password-protected galleries.
- Any change to caching keys, TTLs, invalidation logic, or cache layer (in-memory, Redis, HTTP cache headers).
- Any change to downstream sync targets — WordPress, Next.js/Nuxt CMS pipeline, CDN, image-processing pipeline.
- Any change to EXIF/IPTC metadata propagation or asset transformation.
- Any Zenfolio-side structural change announced to the integration owner (API behavior notice, endpoint migration, TLS cert rotation).
- Restored deployment after a gallery processing incident or rollback.
- **Extended dormancy** — the integration has not executed against Zenfolio in long enough for tokens, proxy state, or upstream gallery shape to have drifted.

### Non-Triggers

- Frontend styling changes that do not alter API calls, URL parsing, or response handling.
- Copy changes on gallery-browser UI labels, error messages, loading states.
- Log level, metric label, or observability-only adjustments.
- TypeScript type comment updates that do not change runtime field access.
- React Query stale time tuning **within validated bounds**.

### Validation Categories

Every shakedown must exercise and verify **every category below**. A shakedown that skips a category is incomplete.

| Category | What is verified |
|:---------|:-----------------|
| **API client state** | Client instantiates with correct endpoint, sets `X-Zenfolio-User-Agent`, uses JSON-RPC with positional parameters. An unauthenticated sanity call (`LoadPublicProfile` on a known public owner) succeeds **before** any authenticated call |
| **OAuth token refresh** | Challenge-response auth (`GetChallenge` + `Authenticate`) produces a token. Token cached server-side only. Simulated 20-hour-old token triggers proactive refresh. A 401 during a shakedown call triggers one re-authentication and retry, then succeeds. **The token never appears in any frontend-delivered payload** during the shakedown |
| **Image pipeline integrity** | Test gallery loaded via `LoadPhotoSet(includePhotos=true)`. Every photo URL (thumbnail, medium, large, XLarge, XXLarge) is fetchable over HTTPS. **At least one asset is downloaded in full and verified by byte-count and SHA-256 against the recorded known-good value.** EXIF and IPTC fields match recorded known-good metadata (IPTC caption, EXIF capture time, embedded keywords) |
| **Downstream sync targets** | If integration propagates to WordPress, CMS, or CDN, the shakedown executes a full round-trip with the test gallery's photos. Downstream object count matches source photo count. Downstream cache keys populated. **A second shakedown run does not create duplicates downstream** |
| **Hierarchy traversal** | `LoadGroupHierarchy` returns expected root group shape. The recorded known path (Root Group → test subgroup → test gallery) resolves by ID and by `CustomReference` without error. Gallery `Type` (Gallery vs Collection) matches the recorded known value |
| **Rate-limit backoff** | A bounded burst (10-20 sequential `LoadPhoto` calls within one second) executes without triggering a long block. If the client-side rate limiter queues or delays requests, the queue behavior is observed and recorded. **No request fails with a 429-equivalent outcome** within the shakedown burst |
| **Error recovery** | A synthetic 5xx response (induced via fault injection on the proxy, or by pointing the proxy at an unreachable host for one call) triggers exponential backoff with jitter, **at most 3 retry attempts**, and a circuit-breaker-aware error surface. Verifies retry count, delay envelope, final classification as transient |
| **Access descriptor enforcement** | A private gallery in the test account is **confirmed not to appear in any public-facing proxy response** during the shakedown. A password-protected test gallery requires a keyring unlock before its photos return. `KeyringGetUnlockedRealms` reflects the unlocked state after `KeyringAddKeyPlain` |
| **Cache invalidation** | After a mutation on the test gallery (`UpdatePhotoSet` title change, or `UpdatePhoto` caption change) executes through the proxy, **the affected cache entries are invalidated**. The next read returns the mutated value, not the stale cached value. A related but unaffected gallery's cache entry remains intact |

### Execution Principles

- **Conservative execution** — Exactly **one designated test gallery** with a known structure, bounded photo count (typically 10-20 photos), known-good EXIF/IPTC metadata recorded in the reference fixture. **No traversal of the full account tree, no bulk downloads, no stress on the Zenfolio API.**
- **Progressive stress** — Execute the simplest read path first (`LoadPrivateProfile` or `LoadPublicProfile`), then hierarchy traversal, then single photo fetch, then full gallery load, then downstream propagation, then rate-limit burst. **Stop at the first failure and diagnose** before proceeding.
- **Controlled environment** — Dedicated shakedown Zenfolio account or a dedicated shakedown gallery. Credentials from secret store. Proxy pointed at a **staging cache layer**, not production. Downstream targets pointed at **staging CMS/CDN, not production**.
- **Observable execution** — Every Zenfolio API call logged with method name, `IncrementalLevel`, response time, cache hit/miss, HTTP status. Every downloaded asset logged with byte count and hash. Every downstream write logged with target ID and timestamp.
- **Known-good inputs** — Fixed test gallery ID, fixed test photo IDs, recorded known-good hash and metadata for at least one asset, recorded expected gallery structure. **The reference fixture is version-controlled alongside the integration code.**
- **No optimization during shakedown** — Do not tune cache TTLs, retry counts, or batch sizes while the shakedown runs. **Note the observation, log it, move on.** Optimization introduces changes that themselves require shakedown.

### Execution Pattern

Execute these steps in order. Do not reorder. Do not skip.

1. **Confirm preflight passes**: credentials in secret store, proxy reachable, DNS resolves, TLS chain verifies, reference fixture loaded.
2. **Initialize controlled environment**: clear proxy cache entries for the test gallery and its parent group, clear downstream staging target of prior shakedown artifacts, acquire a fresh authentication token.
3. **Execute the simplest end-to-end path**: unauthenticated sanity call, then authenticated `LoadGroupHierarchy`, then `LoadPhotoSet` on the test gallery with `includePhotos=true`.
4. **Verify outputs**: returned gallery structure matches reference fixture; photo count matches; `TitlePhoto` ID matches; sample photo URL fields populated.
5. **Check for leaks and orphans**: token cached exactly once, no duplicate downstream writes, no dangling keyring entries, no open connections past their expected lifetime.
6. **Increase complexity**: byte-level asset download and hash verification, EXIF/IPTC round-trip check, rate-limit burst, synthetic 5xx recovery, password-protected gallery keyring unlock, mutation-plus-cache-invalidation round-trip, full downstream sync.
7. **Record all observations**: API call log, response times, cache hit ratio, downstream write log, asset hash results, metadata diff report.
8. **Classify results**: pass, fail-blocking, fail-nonblocking, inconclusive.

### Reference Shakedown Harness (TypeScript)

```ts
// zenfolio-shakedown.ts — known-good test gallery validator
// Usage: ts-node zenfolio-shakedown.ts (reads ZENFOLIO_USER / ZENFOLIO_PASS from secret store)
import { createHash } from 'node:crypto';
import { strict as assert } from 'node:assert';

interface ShakedownFixture {
    testGalleryId: number;
    expectedPhotoCount: number;
    expectedTitlePhotoId: number;
    referenceAssetPhotoId: number;
    referenceAssetSha256: string;
    referenceAssetByteCount: number;
    referenceCaption: string;
}

async function runZenfolioShakedown(fixture: ShakedownFixture) {
    // 1. Challenge-response auth via proxy (token never touches this process's stdout)
    const tokenHandle = await zfProxy.authenticate();
    assert.ok(tokenHandle.cachedServerSide, 'token must remain server-side');

    // 2. Hierarchy traversal
    const hierarchy = await zfProxy.loadGroupHierarchy();
    assert.ok(hierarchy.Elements?.length, 'hierarchy must contain at least one element');

    // 3. LoadPhotoSet with includePhotos for the test gallery
    const gallery = await zfProxy.loadPhotoSet(fixture.testGalleryId, {
        level: 'Level2',
        includePhotos: true,
    });
    assert.equal(gallery.Photos.length, fixture.expectedPhotoCount,
        `expected ${fixture.expectedPhotoCount} photos, got ${gallery.Photos.length}`);
    assert.equal(gallery.TitlePhoto?.Id, fixture.expectedTitlePhotoId,
        'TitlePhoto drift detected — fixture is stale or gallery was edited');

    // 4. Byte-level asset verification against known-good hash
    const referencePhoto = gallery.Photos.find((p) => p.Id === fixture.referenceAssetPhotoId);
    assert.ok(referencePhoto, 'reference photo missing from test gallery');
    const bytes = await zfProxy.downloadAsset(referencePhoto.OriginalUrl);
    assert.equal(bytes.byteLength, fixture.referenceAssetByteCount, 'asset byte count drift');
    const sha = createHash('sha256').update(bytes).digest('hex');
    assert.equal(sha, fixture.referenceAssetSha256, 'asset hash drift — asset was re-encoded or replaced');

    // 5. EXIF/IPTC round-trip — verify caption propagation through the pipeline
    const meta = await zfProxy.extractIptc(bytes);
    assert.equal(meta.caption, fixture.referenceCaption, 'IPTC caption propagation failure');

    // 6. Rate-limit burst — 15 sequential LoadPhoto calls, none must fail
    for (let i = 0; i < 15; i += 1) {
        const photo = gallery.Photos[i % gallery.Photos.length];
        await zfProxy.loadPhoto(photo.Id, 'Level1');
    }

    // 7. Cache invalidation round-trip
    const originalCaption = gallery.Caption ?? '';
    await zfProxy.updatePhotoSet(fixture.testGalleryId, { Caption: `shakedown-${Date.now()}` });
    const refreshed = await zfProxy.loadPhotoSet(fixture.testGalleryId, { level: 'Level2', includePhotos: false });
    assert.notEqual(refreshed.Caption, originalCaption, 'cache invalidation failed on mutation');
    await zfProxy.updatePhotoSet(fixture.testGalleryId, { Caption: originalCaption });

    return { classification: 'pass', photoIdsVerified: gallery.Photos.map((p) => p.Id) };
}
```

### Result Classification

| Outcome | Trigger |
|:--------|:--------|
| **Pass** | All validation categories succeeded. Integration executes correctly against the test gallery. **Proceed to production gallery processing** |
| **Fail-blocking** | A critical integration path failed: auth could not acquire a token, `LoadPhotoSet` returned a structurally different shape from the fixture, asset hash did not match, EXIF/IPTC dropped or corrupted, downstream sync wrote duplicates, **private galleries leaked through the proxy**, or keyring flow failed. **Do not enable production processing.** Fix the defect. **Re-run shakedown from step 1** |
| **Fail-nonblocking** | An observed anomaly that does not prevent correct operation but requires attention: elevated response time, cache hit ratio below expected baseline, non-critical log spam, downstream write latency exceeding the target. Log to issue tracker with reproduction context. **Production processing may proceed with explicit sign-off** |
| **Inconclusive** | Test environment did not permit validation: test gallery unreachable, downstream staging target offline, reference fixture out of date. Adjust environment or fixture and re-run the specific validation |

### Required Artifacts

A shakedown without artifacts **did not happen**.

- **Execution log** — Full timestamped log of every Zenfolio API call with method name, parameters, response time, cache hit/miss, HTTP status, truncated response shape. Every downloaded asset with byte count and hash. Every downstream write with target ID.
- **Result summary** — Pass/fail classification per validation category with the specific photo IDs, photoset IDs, and downstream target IDs that drove each classification.
- **Issue list** — Every anomaly observed, classified blocking/non-blocking/deferred, with reproduction context (gallery ID, photo ID, timestamp, response snapshot).
- **Environment snapshot** — Zenfolio API version (1.8), proxy commit SHA, secret store version fingerprint (not the secret), reference fixture version, downstream target versions, Node/runtime version.

### Known-Good Fixture

**The reference fixture for the shakedown** (test gallery ID, expected photo count, expected `TitlePhoto` ID, recorded asset hash, recorded EXIF/IPTC values) **is version-controlled alongside the integration source code**. Drift between the fixture and the test gallery must be detected by the shakedown and **reported as inconclusive**, not silently tolerated.

### Anti-Patterns

- **Skipping shakedown** because a change "only touched the URL parser" or "only updated the cache key format". Changes that touch Zenfolio integration boundaries always warrant shakedown.
- **Treating shakedown as an exhaustive test suite** that loads every gallery in the account. Shakedown uses one designated test gallery with known-good reference data.
- **Running the shakedown against a recorded JSON-RPC fixture or an in-memory stub.** Shakedown requires the **real Zenfolio API**. Mocks hide integration faults including TLS, DNS, rate limit, and API version drift.
- **Pointing the shakedown's downstream sync at the production target.** Shakedown is bounded to staging targets.
- **Tuning cache TTLs, retry counts, or batch sizes while the shakedown is running.** Note the issue, move on, optimize after shakedown passes.
- **Declaring shakedown passed without preserving the four artifacts.**

---
[Back to Overview](./OVERVIEW.md)
