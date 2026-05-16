# Multi-Factor Authentication

MFA requires two or more independent authentication factors:
- Something the user **knows** (password)
- Something the user **has** (authenticator app, hardware key)
- Something the user **is** (biometric)

### MFA Required for Admins

**Require MFA for all administrative accounts** (platform admin, IdP admin, infrastructure admin, database admin). A compromised admin account without MFA enables complete system takeover.

### Factor Preference (Strongest First)

| Factor | Phishing-Resistant? | Notes |
|:-------|:--------------------|:------|
| FIDO2 / WebAuthn (hardware key) | Yes | Origin-bound cryptography |
| Platform authenticator (Touch ID, Windows Hello) | Yes | Origin-bound cryptography |
| TOTP (authenticator app) | No | Phishable |
| SMS OTP | No | SIM swapping, interception |

### Step-Up Authentication

A user authenticated with password + TOTP may access general resources, but modifying payment methods, changing email, or exporting data requires re-authentication or an additional factor. Step-up avoids MFA fatigue for routine operations while protecting critical actions.

### Recovery

Provide recovery for lost MFA devices:
- Recovery codes (generated during enrollment, stored securely by user) — single-use, treat as high-sensitivity secrets
- Backup MFA methods (secondary authenticator app, backup hardware key)
- Supervised identity verification by an administrator

---
[Back to Overview](./OVERVIEW.md)
