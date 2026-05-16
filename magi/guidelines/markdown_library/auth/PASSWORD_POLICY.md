# Password Policy and Credential Storage

When applications manage passwords directly (not delegated to an IdP), credential storage and policy enforcement must follow established cryptographic and usability standards.

### Password Hashing

- **Argon2id** (preferred for new implementations)
- **bcrypt** (cost factor 12+)
- **scrypt**

**Never** use MD5, SHA-1, SHA-256, or any non-memory-hard hash for password storage. Fast hashes enable brute-force attacks that test billions of candidates per second.

### Salting

Use a unique, random salt per password. The hashing library generates and embeds the salt automatically. **Never use a shared or application-wide salt.**

### Password Policy (NIST SP 800-63B Aligned)

- Minimum length: **12 characters**
- Maximum length: **do not impose below 128 characters**
- **No composition rules** (no "must contain uppercase, lowercase, number, symbol") — NIST recommends against composition rules as they reduce password space without improving security
- Check against breach databases (Have I Been Pwned API) to reject commonly compromised passwords

### Password Hygiene

- **Never log, display, or transmit plaintext passwords.**
- Mask password fields in forms.
- Exclude password parameters from request logging.
- Transmit passwords over TLS exclusively.
- After hashing, discard the plaintext password from memory immediately.

---
[Back to Overview](./OVERVIEW.md)
