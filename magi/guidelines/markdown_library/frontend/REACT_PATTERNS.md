# React 19+ Patterns

### `use()` Hook for Async Data

```tsx
import { use, Suspense } from 'react'

function UserProfile({ userPromise }: { userPromise: Promise<User> }) {
  const user = use(userPromise)
  return <div>{user.name}</div>
}

function App() {
  return (
    <Suspense fallback={<Loading />}>
      <UserProfile userPromise={fetchUser()} />
    </Suspense>
  )
}
```

### Server Components Boundary

```tsx
// Mark client components explicitly
'use client'
import { useState } from 'react'

export function InteractiveComponent() {
  const [count, setCount] = useState(0)
  return <button onClick={() => setCount(count + 1)}>{count}</button>
}
```

### React Compiler Compatibility

Code patterns must remain compatible with the React Compiler. Forbidden:

- Direct state mutations.
- Side effects in render.
- Conditional hooks (call hooks at top level only).

---
[Back to Overview](./OVERVIEW.md)
