# Deployment

### web.xml Configuration

Configure `WicketFilter` with `applicationClassName` parameter pointing to `WebApplication` subclass. Map filter to `/*` or application-specific path. Configure session timeout appropriate for application requirements.

### Development vs Production Mode

Configure via `wicket.configuration` context parameter or system property.

| Mode | Behavior |
|:-----|:---------|
| **Development** | Detailed error pages, Ajax debug window, markup hot reloading, strict serialization checks |
| **Production** | Generic error pages, optimized rendering, resource caching, stripped wicket tags |

### Clustering Configuration

For clustered deployments:

- Ensure all page data is serializable.
- Configure session replication on application server.
- Use `LoadableDetachableModel` consistently.
- Minimize session size.
- **Test serialization thoroughly in development with `CheckingObjectOutputStream`.**

---
[Back to Overview](./OVERVIEW.md)
