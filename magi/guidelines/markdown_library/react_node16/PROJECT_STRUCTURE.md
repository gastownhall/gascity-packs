# Project Structure

Project structure determines how quickly developers find code, how modules depend on each other, and how the application scales as features are added.

### Feature-Based Organization

Organize by feature, not by technical layer. A feature directory contains its components, hooks, types, utilities, tests, and styles:

```text
src/
├── features/
│   ├── auth/
│   │   ├── LoginForm.tsx
│   │   ├── useAuth.ts
│   │   ├── auth.types.ts
│   │   ├── LoginForm.test.tsx
│   │   └── index.ts
│   └── product/
│       ├── ProductCard.tsx
│       ├── useProduct.ts
│       └── index.ts
├── shared/
│   ├── components/
│   ├── hooks/
│   └── lib/
└── App.tsx
```

This reduces the mental overhead of navigating across `components/`, `hooks/`, `types/`, `utils/` directories to find related code. Shared code (common components, global types, utility functions) lives in a `shared/` or `lib/` directory.

### Path Aliases

Use path aliases (`@` or `~`) for absolute imports:

```typescript
import { Button } from '@/components/ui/Button';
```

Configure in `tsconfig.json` (`paths`) and the bundler (Vite `resolve.alias`). Path aliases eliminate fragile relative imports (`../../../../components/Button`) and make refactoring (moving files) less disruptive to import paths.

### Barrel Exports

Use barrel exports (`index.ts`) at the **feature directory level** to provide a clean public API:

```typescript
// src/features/auth/index.ts
export { LoginForm } from './LoginForm';
export { useAuth } from './useAuth';
export type { AuthState } from './auth.types';
```

Consumers import from the feature directory:

```typescript
import { LoginForm, useAuth } from '@/features/auth';
```

**Do not create deeply nested barrel exports** that re-export from other barrels — this creates circular dependency risks and obscures the actual import source.

---
[Back to Overview](./OVERVIEW.md)
