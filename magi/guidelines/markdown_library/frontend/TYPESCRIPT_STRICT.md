# TypeScript 5.x Strict Patterns

### `satisfies` Operator

Use `satisfies` for type narrowing without losing inference:

```typescript
const config = {
  port: 3000,
  host: 'localhost',
  ssl: true
} satisfies ServerConfig

// config.port is number, not ServerConfig['port']
const port = config.port + 1 // Type inference preserved
```

### Const Type Parameters

Use const generics for literal inference:

```typescript
function createConfig<const T extends ReadonlyArray<string>>(items: T): T {
  return items
}

const fruits = createConfig(['apple', 'banana'] as const)
// Type is readonly ['apple', 'banana'], not string[]
```

### Safe Indexed Access

With `noUncheckedIndexedAccess`:

```typescript
const items = ['a', 'b', 'c']
const item = items[0] // Type is string | undefined

if (item) {
  console.log(item.toUpperCase()) // item is string here
}

// Or use non-null assertion when certain
const firstItem = items[0]!
```

### Type Definitions

```typescript
export interface Event {
  id: string
  title: string
  sport: Sport
  date: string
  location: Location
  status: EventStatus
  thumbnailUrl: string
  photoCount: number
}

export type Sport = 'football' | 'basketball' | 'baseball' | 'soccer' | 'volleyball' | 'other'
export type EventStatus = 'upcoming' | 'available' | 'past'

export interface Location {
  venue: string
  city: string
  state: string
  address?: string
}

export interface EventFilters {
  sport?: Sport
  status?: EventStatus
  date?: Date
  searchQuery?: string
}

export interface ApiResponse<T> {
  data: T
  message?: string
}

export interface ApiError {
  message: string
  code: string
  details?: Record<string, string[]>
}
```

**TypeScript Rules:**

- Enable strict mode in `tsconfig.json`.
- Never use `any`; use `unknown` if type truly unknown.
- Define interfaces for all data structures.
- Use `type` for unions and simple aliases.
- Export types alongside implementation files.
- Use const assertions for literal types.
- Use utility types (`Pick`, `Omit`, `Partial`, `Required`) to derive types.
- Define branded types for IDs to prevent mixing different ID types.
- Use `satisfies` operator for type narrowing without losing inference.

---
[Back to Overview](./OVERVIEW.md)
