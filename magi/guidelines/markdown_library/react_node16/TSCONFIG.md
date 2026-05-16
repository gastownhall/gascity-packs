# TypeScript Compiler Configuration

The `tsconfig.json` is the type system's constitution. Every flag affects what the compiler catches and what it allows through. Configuration is not a one-time setup — it evolves as TypeScript releases new strictness options.

### Compiler Target

Set `target` to ES2020 or higher. ES2020 provides optional chaining, nullish coalescing, BigInt, `Promise.allSettled`, and `globalThis` as native emit targets rather than polyfilled output.

| Project type | Target |
|:-------------|:------:|
| Node 20+ backend | `ES2022` |
| Browser-only frontend bundled via Vite/Webpack | `ESNext` (let the bundler downlevel) |

### Module Resolution

Set `moduleResolution` to `bundler` (TypeScript 5+) for Vite-based projects or `node16`/`nodenext` for Node.js projects. The legacy `node` resolution mode does not support `package.json` `exports` fields, conditional exports, or ESM imports correctly. `bundler` resolution matches how Vite, Webpack 5, and esbuild resolve modules, eliminating false-positive import errors.

### Required Flags

| Flag | Purpose |
|:-----|:--------|
| `verbatimModuleSyntax` | Enforce explicit type-only imports (`import type { User } from './types'`); prevents runtime import of type-only modules that get elided during compilation but trigger side effects during bundling |
| `isolatedModules` | Compatibility with transpile-only tools (Vite, esbuild, SWC, Babel); prohibits `const enum`, namespace merging, type-only re-exports without the `type` keyword |
| `skipLibCheck: true` | Skip type checking of `.d.ts` files in `node_modules`; reduces compilation time 30–60% on large projects without affecting your code's type safety |

### Reference tsconfig.json

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "strict": true,
    "noUncheckedIndexedAccess": true,
    "exactOptionalProperties": true,
    "noImplicitOverride": true,
    "verbatimModuleSyntax": true,
    "isolatedModules": true,
    "skipLibCheck": true,
    "jsx": "react-jsx",
    "esModuleInterop": true,
    "forceConsistentCasingInFileNames": true,
    "resolveJsonModule": true,
    "paths": {
      "@/*": ["./src/*"]
    }
  }
}
```

---
[Back to Overview](./OVERVIEW.md)
