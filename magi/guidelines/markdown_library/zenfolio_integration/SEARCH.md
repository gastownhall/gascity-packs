# Search and Discovery

Zenfolio search operates on **public content and content accessible to the authenticated user**.

### Search Methods

| Method | Returns |
|:-------|:--------|
| `SearchSetByText` | Gallery search — `PhotoSet` objects matching the query against titles, captions, keywords |
| `SearchPhotoByText` | Photo-level search |
| `GetPopularPhotos` / `GetPopularSets` | Trending content |
| `GetRecentPhotos` / `GetRecentSets` | Newest content |
| `GetCategories` | Zenfolio category taxonomy |

Each method returns a limited result set — implement client-side pagination or repeated queries with offset for complete results.

### Search UI Hygiene

- **Debounce search queries** by 300-500ms to avoid firing a request per keystroke.
- Display a loading indicator during search.
- **Cache recent search results** with a short TTL (2-5 min) so repeated searches for the same query return instantly.

### Categories

Use `GetCategories` to load the Zenfolio category taxonomy. Categories are numeric IDs with corresponding display names. Map category IDs from `PhotoSet` and `Photo` objects to display names for filtering UIs. **Cache the category list with a long TTL (24 hours)** — categories change very rarely.

---
[Back to Overview](./OVERVIEW.md)
