# Access Control

Every Group, PhotoSet, and Photo carries an `AccessDescriptor` that governs visibility and interaction permissions. Access types include **Public**, **Private** (owner only), **Password** (anyone with the gallery password via keyring), and **UserList** (specific Zenfolio users). **Access control is hierarchical** — child objects can inherit from their parent or override.

### Filter Private Content from Public Responses

**Check the `AccessDescriptor` on every object before rendering or exposing its data.** A public gallery listing endpoint must not expose private galleries returned by an authenticated API call.

**Authenticated API calls return all galleries including private ones** — the proxy must strip private galleries from responses destined for public frontend consumption unless the viewer is the authenticated owner.

### Inheritance via SameAsContaining

**Respect the `SameAsContaining` flag on `AccessDescriptor`.** When `true`, the object inherits access settings from its parent group or gallery. **Evaluate the effective access by walking up the hierarchy** until an object with explicit (non-inherited) settings is found.

**Caching must account for this inheritance** — changing a parent group's access settings changes the effective access of all inheriting children.

### Metadata Visibility Flags

Access control attributes on the `PhotoSet` control what metadata is disclosed:

- `HideDateCreated`
- `HideVisitCount`
- `HideOwner`

**Respect these flags in the UI.** If `HideVisitCount` is `true`, do not display the view count, even though the API returns it to an authenticated caller.

### Password-Protected Headless Flow

For password-protected galleries in a headless frontend, implement a password entry UI that calls the **server-side proxy's keyring endpoint**. The proxy calls `KeyringAddKeyPlain`, returns the updated keyring (or a session-scoped proxy token), and the frontend retries the gallery load. **Do not send the gallery password directly to the Zenfolio API from client-side JavaScript** — route it through the proxy to maintain the keyring server-side.

---
[Back to Overview](./OVERVIEW.md)
