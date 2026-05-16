# TypeScript Type System

### `any` Is Prohibited

Use `unknown` for genuinely unknown values and narrow with type guards. Use `Record<string, unknown>` for objects with unknown shape. Use the specific type when the shape is known. **Every `any` is a hole in the type system that allows silent runtime failures.**

### Type Assertions (`as`) Are Restricted

`as` is prohibited **except at trust boundaries** (API responses, `JSON.parse`, third-party library returns) where runtime validation accompanies the assertion. Use **zod**, **valibot**, or **io-ts** to validate unknown data and infer the TypeScript type from the schema:

```typescript
const UserSchema = z.object({
  id: z.string().uuid(),
  email: z.string().email(),
});

const user: z.infer<typeof UserSchema> = UserSchema.parse(await response.json());
```

A bare `as UserProfile` on a fetch response is an unchecked assumption that will silently produce wrong data when the API changes.

### `@ts-ignore` and `@ts-expect-error` Are Prohibited

In production code. Fix the type error. If the error originates from a third-party library with incorrect types, file an issue and create a local `.d.ts` declaration file with the correct types. **`@ts-expect-error` is acceptable only in test files** verifying that incorrect usage produces a type error.

### `interface` vs `type`

| Use | For |
|:----|:----|
| `interface` | Object shapes that may be extended or implemented |
| `type` | Unions, intersections, mapped types, conditional types, type aliases |

Both are valid for object shapes; the convention provides semantic clarity — `interface` signals an extensible contract, `type` signals a computed or composite type.

### Discriminated Unions for State Modeling

```typescript
type RequestState<T> =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'success'; data: T }
  | { status: 'error'; error: Error };
```

A type with optional fields (`data?: T`, `error?: Error`, `isLoading?: boolean`) allows **impossible states** (`isLoading: true, data: something`) that discriminated unions structurally prevent.

### `as const` and Literal Types

```typescript
const ROLES = ['admin', 'editor', 'viewer'] as const;
type Role = typeof ROLES[number];  // 'admin' | 'editor' | 'viewer'
```

Without `as const`, the array is typed as `string[]`, losing the literal types.

### `satisfies` for Validation Without Widening

```typescript
const config = { port: 3000, host: 'localhost' } satisfies ServerConfig;
```

Validates the shape against `ServerConfig` while preserving the literal types of the values. A direct annotation `const config: ServerConfig` widens the types, losing the literal `3000` and `'localhost'`.

### Template Literal and Branded Types

```typescript
type ApiRoute = `/api/${string}`;

// Branded types for type-safe identifiers
type UserId = string & { readonly __brand: 'UserId' };
```

Branded types prevent accidentally passing an `orderId` where a `userId` is expected, even though both are strings at runtime.

### `readonly` by Default

Prefer `readonly` on all properties and parameters unless mutation is required. Use `Readonly<T>` for entire object types and `ReadonlyArray<T>` (or `readonly T[]`) for arrays. **Mutable properties are the exception that require justification.**

### Generics

- Use generics for reusable, type-safe abstractions: utility functions, data structures, hooks, API clients.
- Name generic parameters descriptively when the function has multiple: `<TInput, TOutput>` over `<T, U>`. Single-parameter generics use `T` by convention.
- Constrain generics with `extends`: `<T extends { id: string }>`.
- **Avoid over-genericizing.** A function that accepts `<T>` but only ever receives `string` is not generic — it's stringly typed with extra syntax.

---
[Back to Overview](./OVERVIEW.md)
