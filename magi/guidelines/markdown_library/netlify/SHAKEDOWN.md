# Post-Deploy Shakedown

### Definition

A Netlify shakedown is the **controlled integration validation run against a deploy preview URL or branch deploy URL** immediately after `netlify deploy` completes and **before promotion to production**. It answers: *Does the artifact Netlify just built and published at this immutable URL actually load, route, execute functions against real downstreams, and emit the expected cache and security headers under controlled conditions?*

A green build log does not prove the deploy works — it proves the build command exited zero.

### Three Distinct Phases

| Phase | Validates |
|:------|:----------|
| Preflight | Build context before the build runs: lockfile present, `NODE_VERSION` pinned, secrets reachable |
| **Shakedown** | The published deploy against its real CDN, real Edge runtime, and real downstreams using known-good requests |
| Testing | Behavior, performance, accessibility, and regression at scale |

Lighthouse runs belong in testing, not shakedown. End-to-end Playwright regressions belong in testing, not shakedown.

### Mandatory Triggers

Shakedown is mandatory before promoting any deploy to production when the PR/branch change touches:

- `netlify.toml`
- `_redirects` or `_headers`
- `netlify/functions/`
- `netlify/edge-functions/`
- Build plugin declarations
- Environment variable scopes
- Framework adapter configuration
- Runtime version pins
- Domain or alias configuration
- Netlify Identity settings

Shakedown runs against the deploy preview URL for PRs and the branch deploy URL for release branches — **never directly against production**.

### Non-Triggers

- Content-only updates within existing routes that have no redirect, header, or function changes.
- Copy edits and image swaps inside already-shipped layouts.
- Documentation-only repository changes that do not alter the publish directory output.

Any change touching routing, headers, functions, or environment configuration requires shakedown regardless of diff size.

### Route Manifest

Shakedown iterates a **version-controlled route manifest** — a small, explicit list of critical URLs with expected status codes, content type, and cache status. The manifest lives at `shakedown/routes.json` or equivalent. It is not generated from the sitemap and not derived from access logs.

```json
[
  { "path": "/",              "expect_status": 200, "expect_cache_status": "hit",  "expect_content_type": "text/html" },
  { "path": "/pricing",       "expect_status": 200, "expect_cache_status": "hit",  "expect_content_type": "text/html" },
  { "path": "/old-pricing",   "expect_status": 301, "expect_location": "/pricing" },
  { "path": "/api/health",    "expect_status": 200, "expect_content_type": "application/json" },
  { "path": "/assets/app.js", "expect_status": 200, "expect_cache_control": "public, max-age=31536000, immutable" }
]
```

### Validation Categories

1. **Redirects and headers** — assert `_redirects` and `_headers` rules fire against the deploy preview URL using `curl -I`. For every redirect, verify the HTTP status (301/302/200 for rewrites) and the `Location` header. For every `_headers` rule, verify every declared header is present with the declared value. **A missing header is a blocking shakedown failure.**
2. **Netlify Functions** — invoke every function touched by the change against its **real downstream services** (sandbox tenants, staging databases, test payment accounts). Mocks defeat the purpose. The function must start, authenticate, execute the happy-path handler, and return a `Response` whose status, shape, and headers match the committed expected output. Background functions are asserted via their side effects.
3. **Edge Functions** — invoke every edge function in the declared routing order. Assert each runs under its real Deno runtime, reads the expected environment variables (Netlify Context, geolocation, request headers), either calls `context.next()` or returns a `Response` as declared, and completes within the 50ms CPU budget. **A silent edge function failure is a blocking shakedown failure** — edge function failures return 500 to the caller with no automatic fallback.
4. **Environment propagation** — issue a known probe against a dedicated `/api/_shakedown/env` function (or equivalent) that returns the **names** (never the values) of the environment variables the function received. Compare the name set to the declared required set.
5. **Build plugin success** — read the deploy log via the Netlify API and verify each plugin's `onPreBuild`/`onBuild`/`onPostBuild`/`onSuccess` hooks reported success and no plugin emitted a warning that was promoted to error. **Plugin silent failures are blocking.**
6. **Cache headers** — assert the CDN serves each asset class with its expected `Cache-Control` and `Netlify-CDN-Cache-Control` headers. Hashed immutable assets MUST return `public, max-age=31536000, immutable`. HTML routes must return the declared CDN cache policy with the expected `Cache-Status` (`hit` for repeat, `miss` for first, `fwd=stale` only where `stale-while-revalidate` is declared). **Cache header drift is blocking** — it corrupts CDN behavior across every subsequent request.
7. **Forms and Identity** — for sites with Netlify Forms, submit a known-good form payload to the preview URL and assert the submission appears in the form dashboard via the Netlify API within the declared window. For Netlify Identity, complete the signup/login flow end-to-end against the Identity service using a test account and assert the token returned is valid and scoped correctly.

### Execution Order

| Step | Action |
|:----:|:-------|
| 1 | Deploy preview URL loads and returns the expected root response |
| 2 | Iterate the route manifest; assert every entry |
| 3 | `_redirects` and `_headers` assertions |
| 4 | Netlify Function round-trips against real downstreams |
| 5 | Edge Function invocations |
| 6 | Environment variable propagation probe |
| 7 | Build plugin log assertions |
| 8 | Cache header assertions |
| 9 | Forms/identity flows if configured |

Stop at the first **fail-blocking** failure and classify. Do not continue to testing if shakedown fails blocking.

### Required Artifacts

Uploaded to the CI system's artifact store:

- Deploy preview URL.
- Deploy ID.
- Commit SHA.
- Full `curl -I` output for every asserted route.
- Function invocation logs captured from the Netlify log stream.
- Diff between actual and expected for every route.
- Environment snapshot (runtime versions from the deploy log, plugin versions, framework adapter version).
- Classification.

Retain for the same window as deploy artifacts. **A shakedown with no captured artifacts did not happen.**

### Result Classification

- **Pass** — every manifest entry matched, every function returned the expected shape, every header matched, every plugin succeeded. Proceed to promote.
- **Fail-blocking** — a route returned an unexpected status, a redirect pointed to the wrong `Location`, a function failed to authenticate downstream, a required header is missing, an edge function 500'd, a build plugin silently failed, or a cache header drifted. **Halt promotion and roll back to the prior locked deploy.**
- **Fail-nonblocking** — a non-critical informational header drifted, a log field renamed, a forms notification is delayed. Open an issue and promote with monitoring.
- **Inconclusive** — the deploy preview URL was unreachable due to network conditions outside Netlify. Re-run shakedown.

### Anti-Patterns (Forbidden)

- Promoting a deploy to production without running shakedown against its preview URL.
- Running shakedown against `localhost` via `netlify dev` instead of the published preview URL.
- Mocking downstream services during function shakedown.
- Running shakedown with a non-representative environment (dev-only env vars, stubbed identity).
- Using the full Playwright regression suite as shakedown.
- Running shakedown only after promotion instead of before.
- Discarding shakedown artifacts at job exit.

### Reference Shakedown Script

```bash
#!/usr/bin/env bash
# Netlify post-deploy shakedown — run after `netlify deploy` completes, before promotion
set -euo pipefail
DEPLOY_URL="${DEPLOY_PRIME_URL:?netlify injects this for preview deploys}"
OUT=".shakedown/$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "${OUT}"
exec > >(tee -a "${OUT}/run.log") 2>&1

echo "shakedown_target=${DEPLOY_URL}"

# 1. Route manifest assertion
jq -c '.[]' shakedown/routes.json | while read -r row; do
  path="$(jq -r '.path' <<<"${row}")"
  want="$(jq -r '.expect_status' <<<"${row}")"
  got="$(curl -sS -o /dev/null -w '%{http_code}' "${DEPLOY_URL}${path}")"
  [[ "${got}" == "${want}" ]] || { echo "FAIL route ${path} got=${got} want=${want}"; exit 1; }
  curl -sS -D "${OUT}/headers-${path//\//_}.txt" -o /dev/null "${DEPLOY_URL}${path}"
done

# 2. Redirect assertion
loc="$(curl -sS -o /dev/null -w '%{redirect_url}' "${DEPLOY_URL}/old-pricing")"
[[ "${loc}" == "${DEPLOY_URL}/pricing" ]] || { echo "FAIL redirect loc=${loc}"; exit 1; }

# 3. Function round-trip against real sandbox downstream
curl -sS -X POST -H "Content-Type: application/json" \
  --data-binary @shakedown/fixtures/submit.json \
  "${DEPLOY_URL}/api/submit" \
  | tee "${OUT}/submit-actual.json" \
  | diff - shakedown/fixtures/submit-expected.json

# 4. Environment propagation probe (function returns NAMES only)
curl -sS "${DEPLOY_URL}/api/_shakedown/env" \
  | jq -er '. as $got | input | [.[] | IN($got[]) ] | all' shakedown/fixtures/expected-env-names.json \
  || { echo "FAIL env vars missing at runtime"; exit 1; }

# 5. Cache header assertion on immutable asset
ch="$(curl -sSI "${DEPLOY_URL}/assets/app.js" | awk -F': ' 'tolower($1)=="cache-control"{print $2}' | tr -d '\r')"
[[ "${ch}" == *"immutable"* ]] || { echo "FAIL cache-control=${ch}"; exit 1; }

# 6. Build plugin success from deploy log via Netlify API
netlify api getDeploy --data "{\"deploy_id\":\"${DEPLOY_ID}\"}" \
  | jq -er '.plugin_state | all(.state == "success")' \
  || { echo "FAIL plugin state"; exit 1; }

echo "shakedown=pass"
```

---
[Back to Overview](./OVERVIEW.md)
