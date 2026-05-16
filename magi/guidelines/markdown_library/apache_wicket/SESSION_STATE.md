# Session and State

### WebSession

Extend `WebSession` for application-specific session data. Store user authentication state, preferences, and locale. Register the custom session class via `Application.newSession()`. Access via the static `get()` method returning the typed session:

```java
public class MyWebSession extends WebSession {

    private Long authenticatedUserId;

    public MyWebSession(Request request) {
        super(request);
    }

    public static MyWebSession get() {
        return (MyWebSession) Session.get();
    }

    public void authenticate(Long userId) {
        this.authenticatedUserId = userId;
        dirty();
    }
}
```

Rules:
- **Minimize session data.** Sessions replicate across cluster nodes. Large sessions degrade performance and reliability.
- **Store IDs, not entities.** Store user ID in session; load user from database when needed using the `LoadableDetachableModel` pattern.
- **Call `dirty()`** when modifying session state for proper cluster replication.

### Page Parameters

Pass data between pages via `PageParameters` (URL parameters). Create with `new PageParameters().add(key, value)`. Access in the page constructor via `params.get(key)`. Use for bookmarkable navigation and RESTful URLs:

```java
mountPage("/orders/${id}", OrderDetailPage.class);

public class OrderDetailPage extends WebPage {
    public OrderDetailPage(PageParameters params) {
        Long orderId = params.get("id").toLong();
        add(new OrderSummaryPanel("orderSummary", new OrderModel(orderId)));
    }
}
```

### Stateless Pages

Mark pages as stateless with `@StatelessComponent` when they don't need server state. Stateless pages don't consume page store space but cannot use back-button navigation. Use for public, read-only content that scales better without session state.

---
[Back to Overview](./OVERVIEW.md)
