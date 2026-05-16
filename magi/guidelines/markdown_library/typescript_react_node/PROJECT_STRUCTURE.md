# Project Structure

### Feature-Based Organization

```text
src/
├── features/
│   ├── auth/
│   │   ├── AuthForm.tsx
│   │   ├── useAuth.ts
│   │   ├── auth.types.ts
│   │   ├── auth.api.ts
│   │   └── auth.test.ts
│   └── dashboard/
└── shared/
    ├── ui/
    └── lib/
```

This is preferable to scattering related files across `src/components/`, `src/hooks/`, `src/types/`, `src/api/`. **Feature-based organization enables finding, modifying, and deleting a feature as a unit.**

### Monorepo Layout

```text
packages/  # Shared libraries (types, utilities, UI components)
apps/      # Deployable applications (frontend, backend, CLI)
```

Use TypeScript project references (`references` in `tsconfig.json`) for cross-package type checking and incremental compilation.

### Path Aliases

```json
// tsconfig.json
{
  "compilerOptions": {
    "paths": {
      "@/*": ["./src/*"]
    }
  }
}
```

```typescript
import { Button } from '@/components/ui/Button';  // Clean
// vs
import { Button } from '../../../components/ui/Button';  // Brittle
```

Configure the bundler (Vite `resolve.alias`, webpack `resolve.alias`) to resolve the same aliases. **Path aliases improve readability and are resilient to directory restructuring.**

---
[Back to Overview](./OVERVIEW.md)
