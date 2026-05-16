# PII Scrubbing and Data Masking

PII scrubbing is the systematic identification and removal or masking of personally identifiable information from session recordings. Scrubbing operates at multiple layers:

| Layer | Purpose |
|:------|:--------|
| Client-side masking | Prevents PII from leaving the browser |
| Server-side scrubbing | Catches PII that bypasses client-side controls |
| Retention-based deletion | Removes recordings containing suspected PII after a defined period |

### Default Masking by SDK

Configure the recording SDK to **mask all text content by default**. Every tool provides this capability:

| SDK | Default-mask Configuration |
|:----|:---------------------------|
| OpenReplay | `defaultInputMode: 'obscured'`, `obscureTextEmails: true`, `obscureTextNumbers: true` |
| FullStory | Private by Default mode |
| Sentry | `maskAllText: true`, `blockAllMedia: true` |
| LogRocket | DOM privacy settings |
| Microsoft Clarity | Automatic PII masking |

Enable the most restrictive default and selectively unmask static content known to be PII-free (navigation labels, headings, marketing copy).

### Form Input Masking

Mask **all** form input fields by default — text inputs, textareas, selects, radio buttons, checkboxes. Apply masking via the SDK's input masking configuration or via CSS class/data attribute annotation.

| Field type | Rule |
|:-----------|:-----|
| Passwords | **Never unmasked under any circumstance** |
| Credit card fields | **Never unmasked under any circumstance** |
| SSN fields | **Never unmasked under any circumstance** |
| Search fields | May be selectively unmasked if business case justifies |
| Quantity selectors | May be selectively unmasked |
| Non-sensitive dropdowns | May be selectively unmasked |

### Media Element Blocking

Block or mask media elements (images, videos, iframes, canvas, SVG) that may contain user-generated content, profile photos, uploaded documents, or personalized advertising:

| Allowed | Blocked |
|:--------|:--------|
| Static brand imagery (logos, product photos, hero images) | User avatars |
| | Uploaded files |
| | Dynamically generated images (charts with user data, personalized banners) |

### Element-Level Masking Annotations

Apply element-level masking using CSS classes or data attributes provided by the SDK:

| SDK | Mask | Block/Hide |
|:----|:-----|:-----------|
| OpenReplay | `data-openreplay-obscured` | `data-openreplay-hidden` |
| FullStory | `fs-mask` | `fs-exclude` |
| Sentry | `data-sentry-mask` | `data-sentry-block` |
| LogRocket | `data-lr-hide` | — |

**Apply these annotations during component development, not as an afterthought during privacy review.** PII masking is a development concern, not a compliance team concern.

### URL and Hash Sanitization

Mask or exclude URL query parameters and hash fragments that contain PII or tokens. Session recordings capture the page URL. URLs like `/user?email=john@example.com` or `/reset-password?token=abc123` leak PII or security tokens into the recording.

| SDK | URL sanitization hook |
|:----|:----------------------|
| OpenReplay | `sanitizeURLs` |
| Sentry | `beforeAddRecordingEvent` |

### Console Sanitization

Console logs may contain debug output with user data, API responses with PII, or error messages with stack traces containing sensitive context. Configure the SDK to mask console output by default or filter specific log patterns. OpenReplay supports network and console sanitization options. Sentry provides `beforeAddRecordingEvent` for filtering console entries.

### Network Request and Response Sanitization

Session replay tools that capture network activity (request URLs, headers, bodies, response status, timing) provide invaluable debugging context but also capture authorization headers, API keys, tokens, and response bodies containing user data. **Every network capture feature must be configured with sanitization rules before enabling.**

#### Header Stripping

Strip the following headers from captured network requests:

- `Authorization`
- `Cookie`
- `Set-Cookie`
- Any custom authentication headers (`X-API-Key`, `X-Auth-Token`)

Most SDKs exclude these by default, but **verify the configuration explicitly**. A single captured `Authorization: Bearer <token>` in a recording is a credential leak.

#### Body Capture

Do **not** capture request or response bodies by default. Body capture is **opt-in**. When enabled for specific endpoints (debugging a form submission, investigating an API error):

- Apply content-type filtering — capture only `application/json`, exclude `multipart/form-data`.
- Apply field-level redaction — mask `email`, `phone`, `address` fields in JSON bodies.
- **Disable body capture in production once debugging is complete.**

#### Endpoint Exclusion

Exclude internal API endpoints that return user-specific data from network capture:

- `/api/user/*`
- `/api/account/*`
- `/api/billing/*`

Capture only endpoints relevant to the debugging or analysis objective. Fewer captured endpoints means less PII exposure surface.

### Server-Side Scrubbing (Defense in Depth)

Server-side scrubbing catches PII leaking past client-side masking. It is **not a substitute** for client-side masking — by the time server-side scrubbing activates, the PII has already traversed the network.

Enable server-side PII pattern matching for:

- Email addresses
- Phone numbers
- Credit card numbers (Luhn-detectable)
- Social security numbers
- IP addresses

Most cloud vendors (FullStory, Sentry, Datadog) provide automatic pattern-based scrubbing on their ingestion pipeline. Self-hosted deployments (OpenReplay) must configure equivalent scrubbing rules in the data pipeline.

Configure custom scrubbing rules for organization-specific PII patterns: internal employee IDs, customer account numbers, order reference formats, domain-specific identifiers.

---
[Back to Overview](./OVERVIEW.md)
