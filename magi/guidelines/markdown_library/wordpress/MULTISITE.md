# Multisite Considerations

### Multisite-Aware Code

Test for `is_multisite()` before network-level functions. Use `switch_to_blog()` / `restore_current_blog()` for cross-site data access. **Always call `restore_current_blog()`** — leaked context causes cross-site data corruption. Network-activated plugins apply across all sites. Site-specific plugins activate individually.

### Network vs Site Options

| Scope | API |
|:------|:----|
| Network settings | `get_site_option()` / `update_site_option()` |
| Site settings | `get_option()` / `update_option()` |
| Transients | Same pattern |

**Mixing these causes settings leakage between sites.** Document which options are network-level and which are site-level.

---
[Back to Overview](./OVERVIEW.md)
