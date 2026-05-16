# Multi-Technology Architectures

Most production systems use multiple storage technologies. The key is clear boundaries.

### Typical E-Commerce Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Application Layer                        │
└─────────────────────────────────────────────────────────────────┘
         │              │              │              │
         ▼              ▼              ▼              ▼
┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
│   Redis     │ │ SQL Server  │ │ Cosmos DB   │ │ Blob Storage│
│   Cache     │ │  Primary    │ │   Catalog   │ │   Images    │
└─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘
     │                 │              │              │
     │                 ▼              │              │
     │         ┌─────────────┐       │              │
     │         │ Service Bus │◄──────┘              │
     │         │   Orders    │                      │
     │         └─────────────┘                      │
     │                 │                            │
     │                 ▼                            │
     │         ┌─────────────┐                      │
     │         │   Worker    │──────────────────────┘
     │         │  Services   │
     │         └─────────────┘
     │
     └──── Session, cart, rate limiting, feature flags
```

**Technology assignments**:
- **SQL Server**: Orders, customers, payments (ACID transactions)
- **Cosmos DB**: Product catalog (read-heavy, document model, global distribution)
- **Redis**: Session, shopping cart, rate limiting, catalog cache
- **Blob Storage**: Product images, invoices, exports
- **Service Bus**: Order processing workflow, notifications

### Clear Ownership Rules

Define which service owns which data:
- Order data: OrderService → SQL Server
- Product data: CatalogService → Cosmos DB
- User profiles: UserService → SQL Server
- Images: CatalogService → Blob Storage
- Sessions: AuthService → Redis

No service directly accesses another service's storage. Cross-service data access goes through APIs.

### Data Synchronization Patterns

When data must exist in multiple stores:

**Event-Driven Sync**:
```
Write to primary → Publish event → Consumers update secondary stores
```

**Change Data Capture**:
```
Database changes → CDC stream → Update search index, cache, etc.
```

**Dual Write (Avoid When Possible)**:
```
Write to Store A → Write to Store B
```
Dual write creates consistency problems. Prefer event-driven sync.

---
[Back to Overview](./OVERVIEW.md)
