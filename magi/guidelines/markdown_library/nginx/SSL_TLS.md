# SSL/TLS Configuration

TLS configuration determines the encryption strength, protocol compatibility, and certificate chain validity for every HTTPS connection. **Weak TLS is worse than no TLS** — it provides a false sense of security while remaining vulnerable to interception.

### Protocols and Ciphers

```nginx
ssl_protocols           TLSv1.2 TLSv1.3;
ssl_ciphers             ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305;
ssl_prefer_server_ciphers on;
```

| Constraint | Rule |
|:-----------|:-----|
| TLS protocols | TLS 1.2 and TLS 1.3 only |
| Forbidden | TLS 1.0, TLS 1.1 (RFC 8996), SSLv2, SSLv3 |
| Cipher key exchange | ECDHE only |
| Cipher AEAD | AES-GCM or ChaCha20-Poly1305 |
| Forbidden ciphers | CBC-mode without AEAD, RC4, 3DES, export ciphers |
| TLS 1.3 ciphers | Fixed by protocol — no manual configuration |
| Server preference | `ssl_prefer_server_ciphers on` for TLS 1.2 |

### Certificate Chain

Provide the full chain in `ssl_certificate` (server cert + intermediates, **not** the root). Missing intermediates cause validation failures on clients without the intermediate cached. Verify with:

```bash
openssl s_client -connect host:443 -servername host
```

Set `ssl_certificate_key` file permissions to 600. Private keys readable by other users enable compromise without server access.

### OCSP Stapling

```nginx
ssl_stapling on;
ssl_stapling_verify on;
ssl_trusted_certificate /etc/nginx/ssl/chain.pem;
```

Provides certificate revocation status without the client contacting the CA — reduces latency and improves privacy.

### Session Resumption

```nginx
ssl_session_cache    shared:SSL:10m;
ssl_session_timeout  1d;
ssl_session_tickets  off;
```

TLS 1.3 uses PSK-based resumption by default. Disable session tickets unless a key rotation strategy is in place.

### DH Parameters

Generate a strong 4096-bit DH parameters file for TLS 1.2 DHE key exchange. Pre-generate during provisioning, not at runtime. TLS 1.3 does not use DH parameters.

```nginx
ssl_dhparam /etc/nginx/dhparam.pem;
```

### Certificate Renewal

Automate via Certbot, acme.sh, or a cloud provider's managed certificate service. Certificates that expire in production cause **total service outage**. Monitor expiry with alerting at 30, 14, and 7 days before expiry.

### TLS 1.3 0-RTT (Early Data)

Set `ssl_early_data off` unless the application explicitly handles 0-RTT replay protection. TLS 1.3 0-RTT data is vulnerable to replay attacks. Enable only for idempotent GET requests with application-level replay mitigation.

---
[Back to Overview](./OVERVIEW.md)
