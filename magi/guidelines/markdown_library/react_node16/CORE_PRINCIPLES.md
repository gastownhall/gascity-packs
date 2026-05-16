# Core Principles

### TypeScript Is Not Optional

Every `.js` file is a `.ts` or `.tsx` file. JavaScript files in a TypeScript codebase are escape hatches that bypass the type system. There is no "we'll add types later." TypeScript's value is proportional to its coverage — a codebase that is 80% typed has 20% of its surface area unprotected, and bugs concentrate in the unprotected 20%. **All new files are TypeScript. All modified files are migrated to TypeScript during modification.**

### Strict Mode, Always

TypeScript's `strict` flag enables nine compiler checks that catch null reference errors, implicit `any` usage, unsafe function calls, and uninitialized properties. Disabling any strict sub-flag weakens the entire type system. `strict: true` is the baseline. Additional flags beyond the strict umbrella (`noUncheckedIndexedAccess`, `exactOptionalProperties`, `noImplicitOverride`) are enabled for maximum safety. **If a library's types are incompatible with strict mode, the library's types are wrong** — file an issue or contribute a fix; do not weaken the compiler.

### Components Are Functions

All React components are function components. Class components are legacy code maintained only until migration is feasible. Function components provide hooks for state and lifecycle, superior TypeScript inference for props and return types, cleaner composition via custom hooks, and compatibility with React's concurrent features (Suspense, `useTransition`, `useDeferredValue`). Class components cannot use hooks, cannot participate in React Compiler optimizations, and represent a fundamentally different mental model that fragments the codebase.

### Composition Over Inheritance

React's component model is compositional:

- Shared logic lives in **custom hooks**, not in base classes.
- Shared UI structure lives in **layout components with children slots**, not in HOC wrappers.
- Shared behavior lives in **render props or hook-based injection**, not in mixins.

Every level of inheritance adds cognitive overhead. Every level of composition adds clarity.

### Type the Boundaries

Every boundary where data crosses a trust or module threshold gets explicit types:

- Component props
- Hook return values
- API responses
- Context values
- Store state
- Route parameters
- Form values
- Environment variables

Internal implementation may leverage inference. Boundaries demand explicit contracts because they are where misunderstandings between producers and consumers manifest as bugs.

### Foundational Rules

- `tsconfig.json` enables `strict: true` plus `noUncheckedIndexedAccess: true`, `exactOptionalProperties: true`, and `noImplicitOverride: true`. **No strict sub-flag is disabled.**
- All React components are function components with TypeScript. **No class components in new code.** Existing class components are migrated to function components during modification.

---
[Back to Overview](./OVERVIEW.md)
