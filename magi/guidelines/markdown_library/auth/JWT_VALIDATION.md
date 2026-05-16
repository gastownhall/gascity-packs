# JWT Validation

JWTs carry identity claims and authorization decisions as signed (JWS) or encrypted (JWE) payloads. JWT validation is the most security-critical code path in token-based authentication. Every validation shortcut is a vulnerability.

### Mandatory Validation Steps

For every JWT, in this order:

1. **Validate signature** against the IdP's published JWKS (`/.well-known/jwks.json`). Use the `kid` header to select the correct key.
2. **Reject `alg: none`.** Configure the JWT library to accept only expected algorithms (`RS256`, `RS384`, `ES256`, `ES384`).
3. **Validate `iss` (issuer)** against the expected IdP issuer URL.
4. **Validate `aud` (audience)** matches the application's `client_id` or API identifier.
5. **Validate `exp` (expiration)** has not passed. Clock-skew tolerance: 30-60 seconds maximum.
6. **Validate `iat` (issued-at)** and **`nbf` (not-before)** when present. Reject tokens issued in the future or not yet valid.

**Never decode JWT payloads without validating the signature first.** Base64-decoding extracts claims from any token, including forged ones. Libraries that provide "decode without verify" are debugging tools only — never use them in production code paths.

### Algorithm Selection

Use **asymmetric algorithms** (`RS256`, `ES256`) for JWTs shared between services. Symmetric algorithms (`HS256`) require sharing the signing secret with every validating service, expanding the attack surface. Asymmetric algorithms allow validation with the public key while only the IdP holds the private key.

### JWKS Caching

Cache JWKS responses with a TTL (typically 1-24 hours). Implement cache invalidation when a JWT references a `kid` not in the cached key set. This handles key rotation: the new key appears in JWKS before the old key is retired.

### Claim Hygiene

JWTs are signed, not encrypted (unless using JWE). The payload is base64-encoded and trivially readable by anyone with the token. **Store user IDs and roles, not email addresses, phone numbers, or personal data.**

---
[Back to Overview](./OVERVIEW.md)
