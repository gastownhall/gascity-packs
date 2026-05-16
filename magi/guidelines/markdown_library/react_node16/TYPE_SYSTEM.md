# Type System Discipline

TypeScript's type system is the primary defect prevention mechanism. Its effectiveness depends on how rigorously it is used. Loose typing (`any`, type assertions, implicit inference at boundaries) creates gaps that bugs exploit.

### `any` Is Prohibited

The `any` type is **prohibited**. Use `unknown` for values of genuinely unknown type and narrow immediately with type guards (`typeof`, `instanceof`, discriminated union checks, zod/valibot parsing). `unknown` forces the developer to prove the value's shape before using it. `any` silently disables type checking for every operation on the value and everything it touches downstream.

### Interface vs Type

| Use | For |
|:----|:----|
| `interface` | Object shapes representing contracts (props, API responses, service interfaces); supports declaration merging |
| `type` | Unions, intersections, utility types, computed types |

Both are valid — the distinction is convention for clarity.

### Discriminated Unions

Use discriminated unions for state machines and variant types. A discriminated union uses a literal type field (`status`, `type`, `kind`) as the discriminant. TypeScript narrows the type automatically in `switch` and `if` statements based on the discriminant value. This **eliminates impossible states at compile time** — a loading state cannot have a `data` field, a success state cannot have an `error` field.

```typescript
type RequestState<T> =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'success'; data: T }
  | { status: 'error'; error: Error };
```

### Type Assertions (`as`)

Minimize type assertions. Every `as` assertion tells the compiler "I know better than you" — and the developer is frequently wrong. Use type guards and narrowing instead.

**Legitimate uses:**

- Asserting a more specific type after a runtime check the compiler cannot follow (DOM element types after `querySelector` with a known selector).
- Asserting `as const` for literal types.

**Never** use `as` to silence type errors without understanding why the error exists.

### `satisfies` Operator

Use the `satisfies` operator (TypeScript 4.9+) for type validation **without widening**:

```typescript
const config = {
  apiUrl: 'https://api.example.com',
  timeout: 5000,
} satisfies Config;
```

`satisfies` validates the shape against `Config` while preserving the literal types of the values. Unlike `const config: Config = { ... }`, which widens string literals to `string`, `satisfies` retains narrower inference while still catching structural errors.

### Generics

Use generics for reusable, type-safe abstractions: hooks, utility functions, data structures, API clients. **Constrain generics with `extends`** when the function requires specific capabilities:

```typescript
function getProperty<T, K extends keyof T>(obj: T, key: K): T[K] {
  return obj[key];
}
```

Unconstrained generics (`<T>` without `extends`) are appropriate only when the function truly operates on any type.

### Runtime Validation

Use **zod** or **valibot** for runtime validation at trust boundaries: API responses, form submissions, URL parameters, `localStorage` reads, any external input. Define the schema once and infer the TypeScript type from it:

```typescript
import { z } from 'zod';

const UserSchema = z.object({
  id: z.string().uuid(),
  email: z.string().email(),
  role: z.enum(['admin', 'user']),
});

type User = z.infer<typeof UserSchema>;
```

This provides compile-time type safety and runtime validation from a single source of truth, eliminating the type/validation drift that occurs when types and validators are defined separately.

### Type Suppressions

Do **not** use `// @ts-ignore` or `// @ts-expect-error` without a comment explaining why the suppression is necessary and a reference to a tracking issue for its removal. Suppressions bypass the type system at the suppressed line. Uncommented suppressions are invisible technical debt. **`@ts-expect-error` is preferred over `@ts-ignore`** because it errors when the suppressed error is fixed, prompting removal.

---
[Back to Overview](./OVERVIEW.md)
