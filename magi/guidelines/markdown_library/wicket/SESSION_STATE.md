# Session and State

### WebSession

Extend `WebSession` for application-specific session data. Store user authentication state, preferences, and locale. Register custom session class via `Application.newSession()`. Access via static `get()` method returning the typed session.

| Constraint | Required |
|:-----------|:---------|
| Minimize data | Sessions replicate across cluster nodes. **Large sessions degrade performance and reliability.** |
| Store IDs, not entities | Store user ID in session; load user from database when needed using `LoadableDetachableModel` pattern |
| Mark dirty | Call `dirty()` when modifying session state for proper cluster replication |

### Page Parameters

Pass data between pages via `PageParameters` (URL parameters). Create with `new PageParameters().add(key, value)`. Access in page constructor via `params.get(key)`. Use for bookmarkable navigation and RESTful URLs.

### Stateless Pages

Mark pages as stateless with `@StatelessComponent` when they don't need server state. **Stateless pages don't consume page store space but cannot use back-button navigation.** Use for public, read-only content that scales better without session state.

---
[Back to Overview](./OVERVIEW.md)
