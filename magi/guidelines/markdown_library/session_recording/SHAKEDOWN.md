# Shakedown — Record→Upload→Playback Validation

### Definition

A session recording shakedown is a **mandatory end-to-end validation** of the full `record → upload → ingest → store → playback` path against a known-good input session **before production recording is enabled or re-enabled** on any modified configuration.

The shakedown drives a **deterministic, scripted browsing session** through:

- The real recording SDK
- The real ingestion endpoint
- The real storage backend
- The real playback renderer

…and verifies that captured DOM/event data, compressed upload, ingest persistence, PII redaction, retention tagging, consent gating, and playback reconstruction all execute correctly as an integrated whole.

**A static review of the SDK configuration is not a shakedown. A unit test that mocks the upload client is not a shakedown.**

### Preflight vs Shakedown vs Testing

| Phase | Question |
|:------|:---------|
| **Preflight** | Are static prerequisites satisfied? (SDK key loaded, ingestion URL configured, CMP reachable, consent category mapped, TLS chain valid, retention variable present, masking classes compiled into bundle) |
| **Shakedown** | Does the full capture → upload → ingest → store → playback pipeline work under real conditions with a known-good session containing known sensitive fields? |
| **Testing** | Does the integration behave correctly across the input space? (browser matrix, device matrix, long-running session stability, consent withdrawal races, concurrency) |

### Mandatory Triggers

Shakedown is mandatory before production recording is enabled after any of:

- First-ever enablement of session recording on a new web property.
- Session recording SDK version upgrade (OpenReplay Tracker, FullStory, Sentry Replay, LogRocket, Clarity, Datadog Session Replay).
- Change to SDK initialization code, CMP consent gating, or SDK configuration (`maskAllText`, `blockAllMedia`, `defaultPrivacyLevel`, `obscureInputEmails`, `sanitizeURLs`).
- Change to PII masking annotations on any form or DOM region.
- Change to network request capture configuration, header stripping rules, body capture opt-in list, or URL exclusion patterns.
- Change to the consent management platform (new CMP vendor, new category mapping, new consent state variable).
- Change to the ingestion endpoint URL, ingress proxy, WAF rules, or TLS termination path.
- Change to the storage backend (self-hosted ClickHouse/blob store, vendor region migration, encryption key rotation).
- Change to retention policy, DSAR deletion workflow, or per-user deletion implementation.
- Change to playback renderer that affects replay reconstruction fidelity.
- Change to route exclusion list, sampling rate, or error-triggered capture configuration.
- SSR/SPA framework upgrade that could affect SDK lifecycle or DOM mutation observation.
- Restored deployment after a PII exposure incident in recordings.
- Extended dormancy on a property whose recording configuration may have drifted.

### Non-Triggers

- Copy changes on the privacy policy page that do not alter recording scope.
- Dashboard user provisioning changes on the recording platform.
- Access log query changes that do not touch capture or storage.
- Cosmetic changes to the player UI within the vendor's managed dashboard.
- RBAC role renames on the recording platform.

### Validation Categories

Every session recording shakedown must exercise and verify every category below. **A shakedown that skips a category is incomplete.**

1. **Capture fidelity** — the scripted known-good session is driven through a real browser (Playwright or Puppeteer) with the recording SDK initialized after consent. The SDK observes every expected DOM mutation and user event. The in-memory captured event stream matches the reference event sequence recorded in the shakedown fixture.
2. **Upload path reliability** — the SDK compresses and transmits the captured session to the ingestion endpoint. A synthetic network failure injected mid-upload (one request forced to return 5xx or be dropped) triggers the SDK's retry path. The full session ultimately reaches the ingestion endpoint. A session that fails all retry attempts is surfaced as a telemetry signal, not silently discarded.
3. **Storage durability** — after upload completes, the ingested session is persisted to the storage backend (ClickHouse event store + blob storage for self-hosted, or the vendor's storage layer). The session ID is queryable within a bounded window (typically under 2 minutes). The stored event count matches the captured event count. The retention tag on the stored session reflects the configured retention period.
4. **Redaction correctness** — the known-good input session deliberately interacts with sensitive fields (password input, credit card number input, SSN input, email input, free-text note containing a synthetic PII marker like `SHAKEDOWN_PII_TOKEN`). Every sensitive field in the stored recording is masked. The synthetic PII marker does not appear in any event body, network capture, console log, or URL field. **A grep for the marker across the full stored session returns zero hits.**
5. **Playback reconstruction** — the stored session is fetched via the playback renderer and rendered in a headless browser. A visual diff against a known-good snapshot of the reference session shows no unexpected content leakage, correct mask rendering over input fields, correct media blocking, and correct route transitions. Minor pixel-level differences on animated elements are tolerated within a documented threshold.
6. **Consent gate enforcement** — the shakedown includes a second scripted session that loads the page **without** granting CMP consent. Browser DevTools network log (captured via Playwright's network interception) must show **zero requests** to the recording vendor's ingestion domain before consent. After consent is granted, the SDK initializes and recording begins. After consent is withdrawn via the CMP preference center, the SDK's stop method is invoked and no further upload requests occur.
7. **PII masking rule firing** — every configured element-level masking annotation is present on the expected DOM nodes in the shakedown page. The SDK honors every annotation — corresponding event payloads contain redacted placeholders, not original text.
8. **Retention policy tagging** — the stored shakedown recording carries the expected retention tag and scheduled deletion timestamp. A manual DSAR-style deletion request for the shakedown user/session completes successfully within the regulatory window and the session is no longer retrievable from any storage layer.
9. **Network header and URL sanitization** — the known-good session triggers network requests containing `Authorization` headers, `Cookie` headers, and a URL with a query parameter named `token=`. The stored network capture has the `Authorization` header stripped, the `Cookie` header stripped, and the `token` query parameter redacted. The response bodies for endpoints not on the opt-in capture list are absent.

### Execution Principles

- **Conservative execution** — one scripted known-good session with fixed steps, fixed field values (synthetic PII only), and a fixed marker string. **No fuzzed input, no real user PII, no load generation.**
- **Progressive stress** — capture → upload → storage query → redaction check → playback → consent gate → deletion. Stop at the first category that fails and diagnose before proceeding.
- **Controlled environment** — dedicated shakedown SDK project key distinct from the production key. Dedicated shakedown tenant on self-hosted deployments. Dedicated shakedown route or subdomain that does not overlap production pages. **Synthetic PII only — never real user data.**
- **Observable execution** — every SDK network request captured by Playwright interception and logged with URL, status, and payload size. Every stored session logged with session ID, event count, size in bytes, and retention tag. Every playback frame diff logged with pixel delta against the reference snapshot.
- **Known-good inputs** — fixed navigation sequence, fixed click targets, fixed keystrokes, fixed synthetic PII marker. The expected captured event stream, stored payload shape, and playback snapshot are recorded in the shakedown fixture and version-controlled.
- **No optimization during shakedown** — do not tune compression, adjust mutation batching, or rewrite the upload retry logic while the shakedown runs. **Note the observation, log it, move on.**

### Execution Order

Execute these steps **in order**. Do not reorder. Do not skip.

1. Confirm preflight passes — shakedown project key loaded, ingestion endpoint reachable over TLS, CMP configured with shakedown consent category, shakedown fixture loaded, reference snapshot available.
2. Initialize the controlled environment — clean prior shakedown sessions from the storage backend, reset the consent state in the test browser context, start Playwright with network interception enabled.
3. Execute the consent-gate sub-case — load the shakedown page without consent, assert zero requests to the ingestion domain, grant consent, assert SDK initialization fires exactly one expected request.
4. Execute the simplest end-to-end path — drive the known-good session script (navigate → type into masked password field with synthetic value → type `SHAKEDOWN_PII_TOKEN` into a masked note field → click through to a second route → stop).
5. Verify outputs — the session ID appears in the storage backend within the bounded window; the event count matches the fixture; the `SHAKEDOWN_PII_TOKEN` marker is absent from the stored payload; network headers are stripped; URL query tokens are redacted.
6. Check for leaks and orphans — no unexpected requests to the ingestion domain before consent, no residual `localStorage`/cookies after consent withdrawal, no partial uploads stuck in a retry queue, no duplicate session IDs.
7. Increase complexity — inject a synthetic 5xx on one upload request and verify retry succeeds; render the stored session through the playback renderer and diff against the reference snapshot; execute a DSAR-style deletion and verify the session is gone.
8. Record all observations — Playwright interception log, storage query results, redaction grep output, playback diff report, consent-gate assertion results.
9. Classify results — `pass`, `fail-blocking`, `fail-nonblocking`, `inconclusive`.

### Result Classification

| Outcome | Trigger |
|:--------|:--------|
| `pass` | All validation categories succeeded — proceed to enable production recording |
| `fail-blocking` | Critical path failed: `SHAKEDOWN_PII_TOKEN` appeared in the stored recording; an `Authorization` header leaked into a captured network request; consent was violated (requests to ingestion domain before consent); the session never reached storage; playback did not reconstruct the reference session; or DSAR deletion did not remove the session from all storage layers. **Do not enable production recording. Fix the defect. Re-run shakedown from step 1.** |
| `fail-nonblocking` | Anomaly does not prevent operation but requires attention: upload latency exceeded the target; playback diff exceeded the documented pixel threshold on a non-sensitive animated region; retention tag applied but with a 24-hour drift from the configured value. Log to issue tracker with reproduction context. Enablement may proceed with explicit sign-off. |
| `inconclusive` | Test environment did not permit validation: playback renderer unavailable; storage backend query API throttled; CMP preference center unreachable. Adjust the environment and re-run the specific validation. |

### Required Artifacts

Every shakedown run produces the following artifacts. **A shakedown without artifacts did not happen.**

| Artifact | Contents |
|:---------|:---------|
| Execution log | Playwright interception log of every request the SDK made, with URL, method, status, payload byte count. Storage backend query responses for the stored session. Redaction grep output across the full stored payload. Playback diff report with pixel delta per frame. |
| Result summary | Pass/fail classification per validation category with the specific session IDs, event counts, and reference snapshot names that drove each classification. |
| Issue list | Every anomaly observed, classified blocking/non-blocking/deferred, with reproduction context (session ID, route, fixture step, timestamp). |
| Environment snapshot | SDK version (OpenReplay Tracker / FullStory / Sentry SDK / LogRocket / Clarity), framework version, CMP vendor and version, ingestion endpoint URL, storage backend version, playback renderer version, shakedown fixture version, reference snapshot hash. |

### Anti-Patterns

- Skipping shakedown because a change "only touched the sampling rate" or "only added a `data-sentry-mask` annotation to one field". **Changes that touch capture, upload, storage, redaction, or playback boundaries always warrant shakedown.**
- Treating shakedown as an exhaustive browser matrix run. Shakedown uses **one** scripted known-good session against **one** reference snapshot.
- Running the shakedown against a mocked SDK, a recorded ingestion response, or a fake storage backend. Shakedown requires the **real** SDK, the **real** ingestion endpoint, and the **real** storage backend.
- Driving the shakedown with real user data copied from production. **Only synthetic PII and the dedicated `SHAKEDOWN_PII_TOKEN` marker are permitted.**
- Writing shakedown sessions to the production storage tenant or production retention index. Shakedown uses a dedicated tenant or project key.
- Tuning compression, batching, or retry parameters while the shakedown is running.
- Declaring shakedown passed without preserving the execution log, result summary, issue list, and environment snapshot.

### PII Token Absence Rule

The `SHAKEDOWN_PII_TOKEN` marker string injected into masked fields during the shakedown **must not appear anywhere** in the stored recording — not in DOM snapshots, not in event payloads, not in network request or response bodies, not in console log captures, not in URL fragments, and not in the playback reconstruction. **Presence of the marker in any of these locations is an automatic `fail-blocking` classification and a reportable configuration defect.**

### Reference Fixture (Playwright)

```typescript
// session-recording-shakedown.ts — record → upload → storage → redaction → playback validator
// Usage: npx playwright test session-recording-shakedown.spec.ts
import { test, expect, type Request } from '@playwright/test';

const SHAKEDOWN_PII_TOKEN = 'SHAKEDOWN_PII_TOKEN_7f3c1';
const INGESTION_HOST = process.env.SHAKEDOWN_INGESTION_HOST ?? 'api.openreplay.com';
const SHAKEDOWN_PAGE = process.env.SHAKEDOWN_PAGE_URL ?? 'https://staging.example.com/shakedown';

test('consent gate holds before acceptance', async ({ page, context }) => {
    const ingestionRequests: Request[] = [];
    page.on('request', (req) => {
        if (req.url().includes(INGESTION_HOST)) {
            ingestionRequests.push(req);
        }
    });
    await context.clearCookies();
    await page.goto(SHAKEDOWN_PAGE);
    await page.waitForTimeout(2_000);
    expect(ingestionRequests, 'SDK must not emit before consent').toHaveLength(0);
});

test('capture upload storage redaction playback end-to-end', async ({ page, request }) => {
    await page.goto(SHAKEDOWN_PAGE);

    // 1. Grant consent via CMP
    await page.click('[data-testid="cmp-accept-all"]');
    const sessionIdPromise = page.evaluate(() =>
        new Promise<string>((resolve) => {
            const id = setInterval(() => {
                const sid = (window as unknown as { __shakedown_session_id?: string }).__shakedown_session_id;
                if (sid) {
                    clearInterval(id);
                    resolve(sid);
                }
            }, 100);
        }),
    );

    // 2. Drive known-good session with synthetic PII marker in a masked field
    await page.fill('[data-openreplay-obscured][data-testid="note"]', SHAKEDOWN_PII_TOKEN);
    await page.fill('[data-openreplay-obscured][type="password"]', 'shakedown-password-value');
    await page.click('[data-testid="submit"]');
    await page.waitForURL('**/shakedown/success');

    const sessionId = await sessionIdPromise;

    // 3. Poll storage backend for the session (bounded 120s)
    const storedSession = await pollStoredSession(request, sessionId, 120_000);
    expect(storedSession.eventCount, 'event count must match fixture').toBeGreaterThan(0);
    expect(storedSession.retentionDays).toBe(90);

    // 4. Redaction check — SHAKEDOWN_PII_TOKEN must not appear anywhere in the stored payload
    const payloadText = JSON.stringify(storedSession.events);
    expect(payloadText, 'PII marker must be fully redacted').not.toContain(SHAKEDOWN_PII_TOKEN);

    // 5. Network header sanitization check
    const capturedNetwork = storedSession.events.filter((e) => e.type === 'network');
    for (const n of capturedNetwork) {
        expect(n.request?.headers?.authorization, 'Authorization header must be stripped').toBeUndefined();
        expect(n.request?.headers?.cookie, 'Cookie header must be stripped').toBeUndefined();
        expect(n.request?.url, 'token query param must be redacted').not.toMatch(/[?&]token=[^&]+/);
    }

    // 6. Playback reconstruction diff against reference snapshot
    const playbackDiff = await renderPlaybackAndDiff(sessionId, 'shakedown-reference.png');
    expect(playbackDiff.pixelDelta).toBeLessThanOrEqual(playbackDiff.allowedThreshold);

    // 7. DSAR deletion verification
    await requestDeletion(request, sessionId);
    await expect(pollStoredSession(request, sessionId, 30_000)).rejects.toThrow(/not found/);
});
```

---
[Back to Overview](./OVERVIEW.md)
