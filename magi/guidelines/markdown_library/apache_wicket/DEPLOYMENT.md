# Deployment

### `web.xml` Configuration

Configure `WicketFilter` with the `applicationClassName` parameter pointing to the `WebApplication` subclass. Map filter to `/*` or an application-specific path. Configure session timeout appropriate for application requirements:

```xml
<filter>
    <filter-name>wicket.app</filter-name>
    <filter-class>org.apache.wicket.protocol.http.WicketFilter</filter-class>
    <init-param>
        <param-name>applicationClassName</param-name>
        <param-value>com.company.app.MyWicketApplication</param-value>
    </init-param>
</filter>
<filter-mapping>
    <filter-name>wicket.app</filter-name>
    <url-pattern>/*</url-pattern>
</filter-mapping>
```

### Development vs Production Mode

Configure via the `wicket.configuration` context parameter or system property:

| Mode | Effect |
|:-----|:-------|
| `development` | Detailed error pages, Ajax debug window, markup hot reloading, `CheckingObjectOutputStream` for serialization checks |
| `deployment` | Generic error pages, optimized rendering, resource caching, stripped `wicket` tags |

### Clustering Configuration

For clustered deployments:
- Ensure all page data is serializable
- Configure session replication on the application server
- Use `LoadableDetachableModel` consistently
- Minimize session size
- Test serialization thoroughly in development with `CheckingObjectOutputStream`

---
[Back to Overview](./OVERVIEW.md)
