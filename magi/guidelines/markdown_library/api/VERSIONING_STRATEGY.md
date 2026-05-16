# Versioning Strategy

### Version Placement

Include version in the URL path as the first segment:

```
/v1/users
/v2/users
```

URL versioning is explicit, visible, and cacheable. Alternative approaches and their trade-offs:

| Strategy | Format | Trade-off |
|:---------|:-------|:----------|
| URL versioning (preferred) | `/v1/users` | Explicit, visible, cache-friendly, easy routing |
| Header versioning | `Accept: application/vnd.api.v1+json` | Less visible, complicates debugging |
| Query parameter | `?version=1` | Easily stripped, cache-unfriendly |

### Version Numbering

- Use **integer major versions only**: `v1`, `v2`, not `v1.2` or `v1.0.0`
- Increment version only for breaking changes
- Multiple versions run concurrently during migration periods
- Sunset old versions with documented timelines (**minimum 12 months warning**)

### Breaking vs Non-Breaking Changes

**Non-breaking (deploy without version bump)**:
- Adding new optional fields to responses
- Adding new endpoints
- Adding new optional query parameters
- Adding new error codes
- Extending enumerations (if clients ignore unknown values)

**Breaking (requires version increment)**:
- Removing or renaming fields
- Changing field types or formats
- Removing endpoints
- Changing URL structure
- Modifying authentication requirements
- Changing error response structure

### Deprecation Process

```text
Step 1: Announce deprecation with sunset date in response headers:
        Deprecation: true
        Sunset: Sat, 01 Jan 2025 00:00:00 GMT
Step 2: Maintain deprecated version fully functional until sunset
Step 3: Document migration path in API documentation
Step 4: Monitor deprecated version usage; contact active consumers
Step 5: Return 410 Gone after sunset date
```

---
[Back to Overview](./OVERVIEW.md)
