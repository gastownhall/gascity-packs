# Data Model and Object Hierarchy

The Zenfolio data model is a tree:

```text
User (root)
└── Groups (recursive nesting)
    └── PhotoSets (Galleries and Collections)
        └── Photos
```

### Galleries vs Collections

| Type | Behavior |
|:-----|:---------|
| **Gallery** | **Physically contains photos** — each photo belongs to exactly one gallery |
| **Collection** | Contains **references** to photos that reside in galleries — a photo can appear in multiple collections but lives in one gallery |

**Deleting a photo from a gallery removes it everywhere, including all collections.** Removing a photo from a collection removes only the reference. Both are `PhotoSet` objects differentiated by the `Type` field.

### Loading the Hierarchy

| Method | Purpose |
|:-------|:--------|
| `LoadGroupHierarchy` | Retrieve full gallery tree for a user — root group with nested sub-groups and photosets. Use for navigation trees, breadcrumbs, gallery browsers. **Cache 15-30 min** since structural changes are infrequent. Invalidate on group creation, deletion, or reorder |
| `LoadPhotoSet(id, includePhotos=true)` | Fetch a gallery and its photos in a single request |
| `LoadPhotoSetPhotos(id, startingIndex, numberOfPhotos)` | Paginated photo loading from large galleries |

**Never load all photos from a 10,000-photo gallery in a single request.** Paginate with **50-100 photos per page** for frontend display.

### Object Identifiers

Photo, PhotoSet, and Group objects are identified by **numeric IDs**. Each object type has its own ID space — a Photo and a PhotoSet can share the same numeric ID. **Always qualify IDs with their object type** in caching keys and internal references:

```text
photo:327977501
photoset:993412712
group:12345
```

### TitlePhoto and PageUrl

- **`TitlePhoto`** on a `PhotoSet` is the cover photo. May be `null` (no cover set) or reference a specific photo. For gallery browsers and grid views, use the `TitlePhoto`'s thumbnail URL. If `null`, use the first photo in the gallery or a placeholder.
- **`PageUrl`** is the web-accessible URL on the photographer's Zenfolio site. Useful for "View on Zenfolio" links and sharing. Image URLs are used for direct rendering in custom UIs.

---
[Back to Overview](./OVERVIEW.md)
