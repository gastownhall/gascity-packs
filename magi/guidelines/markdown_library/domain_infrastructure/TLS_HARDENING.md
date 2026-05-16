# SSL/TLS Configuration and Hardening

### Minimum TLS Version

Enforce **TLS 1.2 minimum**. Disable TLS 1.0 and TLS 1.1 — both are deprecated by RFC 8996 (March 2021). **TLS 1.3 is preferred**: it reduces handshake latency (1-RTT vs 2-RTT), removes obsolete cipher suites, and mandates forward secrecy.

- Cloudflare: set minimum TLS version to 1.2 in SSL/TLS settings.
- Origin servers: disable TLS 1.0 and 1.1 in web server configuration (`nginx ssl_protocols`, Apache `SSLProtocol`, IIS registry settings).

### Cipher Suite Selection

For TLS 1.3, cipher suites are fixed by the specification — all suites use AEAD encryption with forward secrecy. For TLS 1.2:

- Prefer **ECDHE** key exchange (forward secrecy).
- Prefer **AES-GCM** or **ChaCha20-Poly1305** encryption (AEAD).
- Prefer **SHA-256** or **SHA-384** digests.

Forbidden cipher classes:

- RC4
- 3DES
- CBC-mode ciphers without AEAD
- RSA key exchange (no forward secrecy)
- Export-grade ciphers
- NULL ciphers

### HSTS

Deploy HSTS on every production domain.

```http
Strict-Transport-Security: max-age=31536000; includeSubDomains; preload
```

- `max-age=31536000` — one-year duration.
- `includeSubDomains` — extends policy to all subdomains.
- `preload` — eligible for inclusion in browser preload lists, which enforce HTTPS before the first connection.

Submit domains to the HSTS preload list **only after** confirming all subdomains support HTTPS — the `includeSubDomains` requirement means a single HTTP-only subdomain will break all subdomains.

### Cloudflare SSL Modes

Cloudflare proxies traffic in two legs:
1. Client → Cloudflare edge (edge certificate)
2. Cloudflare edge → origin (origin certificate)

The SSL mode controls the second leg. **Full (Strict) is the only acceptable production setting.**

| Mode | Status | Rationale |
|:-----|:-------|:----------|
| Off | Forbidden | No encryption |
| Flexible | Forbidden | Edge encrypts client-to-Cloudflare; Cloudflare-to-origin is plaintext. The most dangerous setting because users see HTTPS in the browser while the origin connection is unencrypted. |
| Full | Forbidden | Encrypts both legs but does not validate the origin certificate; accepts self-signed, expired, or mismatched certificates; susceptible to person-in-the-middle on the origin connection. |
| **Full (Strict)** | **Required** | Encrypts both legs and validates the origin certificate; requires a valid, unexpired certificate on the origin matching the requested hostname. Use either a publicly trusted certificate or a Cloudflare Origin CA certificate on the origin. |

### Origin Certificates

When using Cloudflare as a reverse proxy, install a **Cloudflare Origin CA certificate** on the origin server. These certificates are trusted only by Cloudflare's edge, are free, long-lived (up to 15 years), and require no renewal automation. They cannot be used for direct client connections — only for the Cloudflare-to-origin leg.

Alternatively, install a standard Let's Encrypt or commercial certificate on the origin to enable both Cloudflare-proxied and direct-to-origin connections with valid certificates.

### Authenticated Origin Pulls

Enable authenticated origin pulls to ensure the origin server accepts connections only from Cloudflare's edge. Cloudflare presents a client certificate; the origin server verifies it. This prevents direct-to-origin attacks that bypass the CDN/WAF layer. Configure the origin's web server to require client certificate authentication using Cloudflare's published CA certificate.

---
[Back to Overview](./OVERVIEW.md)
