# BIMI (Brand Indicators for Message Identification)

BIMI enables displaying a brand's verified logo next to authenticated email in supported inboxes (Gmail, Yahoo, Apple Mail, Fastmail, and others). BIMI is the visual reward for achieving DMARC enforcement. It increases brand recognition, recipient trust, and email engagement. BIMI requires DMARC at `p=quarantine` or `p=reject` as a prerequisite.

### Prerequisites

- DMARC at `p=quarantine` or `p=reject` on the organizational domain (not `p=none`).
- SPF and DKIM passing consistently.
- Good sender reputation (not on major blocklists, spam complaint rate below 0.1%).

A BIMI record without DMARC enforcement is ignored by all supporting mailbox providers.

### Logo Format

Prepare the logo in **SVG Tiny P/S (Portable/Secure)** format, not standard SVG. SVG Tiny P/S is a constrained profile that prohibits scripts, external references, and animations. Use the BIMI Group's conversion tools or Adobe Illustrator Export Script to convert standard SVG. Requirements:

- 1:1 aspect ratio
- Centered
- Non-transparent background

Host on a stable HTTPS endpoint with high availability. The URL must be publicly accessible without authentication. Use a CDN or dedicated asset server. Include appropriate `Cache-Control` headers.

### Self-Asserted Record

Start with a self-asserted BIMI record (no certificate) to validate the setup with providers that accept self-asserted logos (Yahoo, Fastmail, AOL):

```dns
default._bimi.example.com.  TXT  "v=BIMI1; l=https://assets.example.com/bimi/logo.svg;"
```

Verify the logo displays correctly in supporting inboxes before investing in a certificate.

### VMC and CMC Certificates

Gmail and Apple Mail require a certificate for BIMI logo display. Two certificate types:

| Certificate | Requirement | Display |
|:------------|:------------|:--------|
| Verified Mark Certificate (VMC) | Registered trademark + identity validation (CA video call) + annual fee | Logo + verified checkmark badge (blue in Gmail, purple in Yahoo) |
| Common Mark Certificate (CMC) | One year of logo usage; no trademark; faster, cheaper | Logo without checkmark |

Both are issued by authorized CAs (DigiCert, Entrust). The BIMI record references the certificate:

```dns
v=BIMI1; l=https://assets.example.com/bimi/logo.svg; a=https://assets.example.com/bimi/vmc.pem;
```

For brands without registered trademarks, evaluate CMC as a stepping stone while pursuing trademark registration for eventual VMC upgrade. Renew certificates before expiry (typically annual). Set renewal reminders 60 and 30 days before expiry.

---
[Back to Overview](./OVERVIEW.md)
