# TypeScript Discipline

### TypeScript Configuration

Nuxt generates `.nuxt/tsconfig.json` that extends the project `tsconfig.json`.

| Setting | Required value |
|:--------|:---------------|
| `strict` | `true` |
| `noUncheckedIndexedAccess` | `true` — catches undefined access on arrays and records |
| `exactOptionalProperties` | `true` — distinguishes between missing and `undefined` |

The Nuxt-generated config provides path aliases (`#imports`, `#app`, `#build`) and auto-import type resolution. **Do not fight the generated config — extend it, do not replace it.**

### Type Patterns

Define shared types in a `types/` directory at the project root. Nuxt auto-imports from this directory when configured. Use `interface` for object shapes that may be extended; use `type` for unions, intersections, and computed types. Export API response types alongside the composables or server routes that produce them. Co-locate types with their consumers when used in a single module; promote to `types/` when shared across modules.

| Surface | Required pattern |
|:--------|:-----------------|
| Props | `defineProps<{ title: string; count?: number }>()`; `withDefaults()` for defaults; **never** the runtime array syntax in new code |
| Emits | `defineEmits<{ submit: [payload: FormData]; cancel: [] }>()` for compile-time payload verification |
| Refs | `ref<User \| null>(null)` when the initial value does not represent the type; let TS infer for `ref(0)` |
| API responses | zod or valibot schemas on the server; infer TypeScript types from the schema; share via shared types package or Nuxt's server type generation |

### Type Narrowing and Guards

Narrow `unknown` and union types **immediately at the boundary** where they enter the application: API responses, route params, form inputs, third-party library returns. Use discriminated unions for state machines (`status: 'idle' | 'loading' | 'success' | 'error'`). Write type-guard functions (`function isUser(value: unknown): value is User`) for complex runtime checks. **Never use type assertions (`as`) to silence errors** — fix the type or add a proper guard.

---
[Back to Overview](./OVERVIEW.md)
