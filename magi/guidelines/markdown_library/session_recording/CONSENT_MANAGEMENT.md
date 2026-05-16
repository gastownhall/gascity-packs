# Consent Management

Session recording falls under non-essential analytics/functional tracking. **GDPR Article 6(1)(a)**, the **ePrivacy Directive Article 5(3)**, **CCPA/CPRA**, and equivalent regulations require prior informed consent before deploying recording SDKs. Consent management is not optional — it is the legal prerequisite for recording to exist.

### CMP Integration

Integrate the session recording SDK with the site's **Consent Management Platform** (CMP): OneTrust, Cookiebot, CookieYes, Osano, or equivalent. The recording SDK script tag or dynamic import is gated behind the CMP's consent state for the analytics or functional tracking category. **The CMP must block the SDK from loading until consent is granted.**

### Tag Manager Gating

Do not load the recording SDK via a tag manager (Google Tag Manager, Segment) without consent gating **inside the tag manager**. GTM alone does not block tags — it fires them based on triggers. Configure the tag to fire only when the consent state variable equals `granted` for the appropriate category. Verify by inspecting network requests with browser DevTools before granting consent: **zero requests** to the recording vendor's domain must appear.

### Consent Withdrawal

When consent is withdrawn (user revokes analytics consent via the CMP's preference center), stop the recording session immediately:

- Call the SDK's stop or disable method.
- Clear any client-side state (cookies, localStorage entries) the SDK created.
- The SDK must not resume recording until consent is re-granted in a future session.

### Jurisdictional Differences

| Jurisdiction | Requirement |
|:-------------|:------------|
| EU/EEA (GDPR) | Explicit opt-in. Pre-ticked checkboxes, implied consent via continued browsing, and consent walls are non-compliant. Accept and Reject **must have equal prominence** |
| California (CCPA/CPRA) | "Do Not Sell or Share My Personal Information" opt-out. Cloud vendor recording = "sale" or "sharing"; self-hosted may not trigger sale provisions but still requires disclosure |
| Other jurisdictions | Organization's default consent model |

Implement **geo-based consent logic**. Geo-detection must be accurate — serving a CCPA-only notice to an EU user is non-compliant with GDPR.

### Privacy Policy Documentation

Document the legal basis for session recording in the privacy policy. Specify:

- What is recorded (user interactions, page content, form inputs in masked form, console errors, network requests).
- The purpose (debugging, UX optimization, conversion analysis).
- The data processor (vendor name or self-hosted).
- Retention period.
- How to exercise data subject rights (access, deletion, portability).

Generic *"we use analytics cookies"* disclosures are insufficient.

### Consent Records

Maintain consent records (timestamp, user identifier or anonymous ID, consent version, categories consented to) for a minimum of **5 years** for GDPR accountability. The CMP should log consent events that can be correlated with session recording data if a data subject requests access or deletion.

---
[Back to Overview](./OVERVIEW.md)
