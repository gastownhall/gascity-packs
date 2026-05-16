# Photo and Gallery Mutations

**Mutating operations (create, upload, update, delete, change access control) require authentication and execute exclusively through the server-side proxy.**

### Creating Galleries

`CreatePhotoSet` accepts:

- Parent group ID.
- PhotoSet type (Gallery or Collection).
- Updater object with `Title`, `Caption`, `Keywords`, `Categories`, `CustomReference`.

**Updater object fields are case-sensitive.** `Title` is required and cannot be empty. `CustomReference` sets the gallery's URL slug on the photographer's Zenfolio site.

### Uploading Photos

Upload via **HTTP PUT to the gallery's `UploadUrl`** (returned in the PhotoSet's `UploadUrl` field):

- PUT request includes the image file as the body.
- `Content-Type` matches the file type (`image/jpeg`, `image/png`, etc.).
- Include `X-Zenfolio-Token` header for authentication.

| Field | Use |
|:------|:----|
| `UploadUrl` | Standard photo uploads |
| `VideoUploadUrl` | Video uploads |
| `RawUploadUrl` | RAW files (API v1.8+) |

**The `UploadUrl` is gallery-specific — do not construct upload URLs manually.**

### Updating Metadata

| Method | Updates |
|:-------|:--------|
| `UpdatePhoto(id, PhotoUpdater)` | Photo metadata (title, caption, keywords, categories) |
| `UpdatePhotoSet(id, PhotoSetUpdater)` | Gallery metadata |

**Both updater objects replace the entire set of keywords and categories on each call — there is no append operation.** To add a keyword, fetch the current keywords, append the new keyword, and send the complete array.

### Delete Operations

`DeletePhoto`, `DeletePhotos`, `DeletePhotoSet`, `DeleteGroup` are **irreversible**.

- Implement confirmation prompts in the UI.
- Consider soft-delete patterns (move to a "Trash" collection before permanent deletion) for integrations that manage gallery content.
- **Log all delete operations** with the authenticated user, timestamp, and deleted object IDs for audit trail.

### Reorder and Move

| Method | Use |
|:-------|:----|
| `MovePhoto` / `MovePhotos` | Reorganize photos between galleries of the same type |
| `ReorderPhotoSet` / `ReindexPhotoSet` | Control photo display order within a gallery |
| `SetPhotoSetTitlePhoto` | Set the cover photo |

All reorder operations require authentication and execute through the proxy.

### Access Control Updates

| Method | Target |
|:-------|:-------|
| `UpdatePhotoAccess` | Photo |
| `UpdatePhotoSetAccess` | PhotoSet |
| `UpdateGroupAccess` | Group |
| `UpdateEventAccess` | Event |

Pass the object ID and an `AccessUpdater` object specifying the new access type, permissions, and password (for password-protected access). **Access control changes may cascade to child objects that inherit settings — verify the intended scope before applying changes.**

---
[Back to Overview](./OVERVIEW.md)
