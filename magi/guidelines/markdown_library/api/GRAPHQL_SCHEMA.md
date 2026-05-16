# GraphQL Schema Design

For APIs choosing GraphQL over REST.

### Schema Organization

| Type | Purpose |
|:-----|:--------|
| `Query` | Read operations |
| `Mutation` | Write operations |
| `Subscription` | Real-time updates |

### Field and Type Naming

- **`camelCase`** for fields
- **`PascalCase`** for types
- **`SCREAMING_SNAKE_CASE`** for enum values

### Nullability

Make fields **non-null by default**. Use nullable for genuinely optional fields:

```graphql
type User {
  id: ID!
  name: String!
  bio: String
  posts: [Post!]!
}
```

`[Post!]!` reads: a non-null list of non-null `Post` items.

### Connection-Pattern Pagination (Relay-Style)

```graphql
type UserConnection {
  edges: [UserEdge!]!
  pageInfo: PageInfo!
  totalCount: Int
}

type UserEdge {
  node: User!
  cursor: String!
}

type PageInfo {
  hasNextPage: Boolean!
  hasPreviousPage: Boolean!
  startCursor: String
  endCursor: String
}
```

### Error Handling via Union Types

Make errors part of the schema rather than relying on the top-level `errors` array for domain failures:

```graphql
union CreateUserResult = User | ValidationError | AuthError

type Mutation {
  createUser(input: CreateUserInput!): CreateUserResult!
}
```

This forces clients to handle each error case explicitly through GraphQL's pattern matching.

---
[Back to Overview](./OVERVIEW.md)
