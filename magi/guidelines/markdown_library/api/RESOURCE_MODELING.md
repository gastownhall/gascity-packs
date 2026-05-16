# Resource Modeling

### Resource Identification

Every API resource requires:
- A unique, stable identifier that never changes after creation
- A canonical URL that serves as the authoritative reference
- Clear boundaries defining what the resource contains versus what it references

### Resource Granularity

Model resources at the granularity that matches client access patterns:

**Coarse-grained resources** reduce round trips but may transfer unnecessary data. Appropriate when clients typically need the full object and partial updates are rare.

**Fine-grained resources** enable precise operations but increase request count. Appropriate when clients operate on specific aspects independently and bandwidth is constrained.

The correct granularity emerges from actual usage patterns. Start coarse; split resources when distinct access patterns emerge.

### Resource Relationships

Express relationships through:
- **Embedding**: Include related data inline when it's always needed together and the relationship is composition (child cannot exist without parent)
- **Linking**: Provide URLs to related resources when data is accessed independently, relationships are associations, or embedded data would cause response bloat
- **Expansion**: Support optional embedding through query parameters (`?expand=author,comments`) for client-controlled payload optimization

### Singleton vs Collection Resources

- **Collection**: `/users` — represents the set of all user resources
- **Singleton**: `/users/{id}` — represents a specific user
- **Nested Collection**: `/users/{id}/orders` — represents orders belonging to a user
- **Singleton Subordinate**: `/users/{id}/profile` — single resource subordinate to parent

**Nesting depth must not exceed two levels.** Beyond that, promote the nested resource to a top-level collection with filtering: `/orders?userId={id}` instead of `/users/{id}/orders/{orderId}/items/{itemId}`.

### Resource State

Resources represent current state, not operations. State transitions occur through standard HTTP methods against the resource. Avoid modeling workflow steps as separate endpoints; model the resource's state and let clients update it.

---
[Back to Overview](./OVERVIEW.md)
