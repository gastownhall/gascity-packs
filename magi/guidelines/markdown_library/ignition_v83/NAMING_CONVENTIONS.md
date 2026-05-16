# Modern Naming Conventions

| Domain | Convention |
|:-------|:-----------|
| Resource type IDs | Lowercase-hyphenated (`database-connection`, `audit-profile`) |
| Path construction | Use `ResourceType.rootPath()` and the resource path API. **Do not concatenate strings.** |
| Qualified identifiers | `QualifiedPath`, `QualifiedValue`, `QualifiedID` — typed identifiers with provider context |
| Historian scripting | `system.tag.history.*` namespace replaces older `system.tag.queryTagHistory` patterns where applicable |

---
[Back to Overview](./OVERVIEW.md)
