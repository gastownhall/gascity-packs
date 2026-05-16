# Keyring and Password-Protected Gallery Access

Zenfolio galleries can be password-protected **independently of account authentication**. A visitor (authenticated or not) must provide the gallery's password to access its contents. The keyring mechanism manages these gallery passwords during a browsing session.

### Adding Keys

Use `KeyringAddKeyPlain` to add a gallery password to a keyring. The method returns an updated keyring string (opaque token). Include the keyring in subsequent requests via:

- `X-Zenfolio-Keyring` header.
- `zf_keyring` cookie.

**The keyring accumulates passwords** — adding a key for Gallery B does not invalidate the key for Gallery A already in the keyring.

### Security Posture

Keyring tokens contain password material (encrypted but sensitive). **Handle keyrings with the same security posture as authentication tokens.** In headless integrations:

- The server-side proxy manages keyrings.
- If the frontend must handle keyrings (for visitor-entered gallery passwords), transmit them over **HTTPS only**.
- **Do not persist them to localStorage or cookies with long expiration.**

### Verifying Unlocked Realms

Use `KeyringGetUnlockedRealms` to verify which access realms (galleries/groups) a keyring currently unlocks. **Useful for UI state**: showing a lock icon on galleries the visitor has not yet unlocked, an open icon on galleries in the current keyring. Cache the unlocked realms alongside the keyring token for the session duration.

### Access Denied Recovery

When a `LoadPhotoSet` or `LoadPhoto` call returns an access denied error for a password-protected gallery:

1. Prompt the user for the gallery password.
2. Call `KeyringAddKeyPlain`.
3. Retry the original request with the updated keyring.

**Do not re-prompt on every request — the keyring persists for the session.**

---
[Back to Overview](./OVERVIEW.md)
