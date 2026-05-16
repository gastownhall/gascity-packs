# Core Principles

### TypeScript Everywhere

Every file in the stack is TypeScript. Frontend components, backend routes, shared utilities, build scripts, configuration files, test files. JavaScript files exist only as build output or for configuration that tooling requires (`.eslintrc.cjs`, `postcss.config.js`). The type system is the first line of defense against bugs — it catches mismatched function signatures, missing properties, incorrect return types, and impossible states at compile time. **A bug caught by `tsc` costs zero runtime. A bug caught in production costs hours.**

### Strict Mode, No Exceptions

`tsconfig.json` enables `strict: true` which activates `strictNullChecks`, `strictFunctionTypes`, `strictBindCallApply`, `strictPropertyInitialization`, `noImplicitAny`, `noImplicitThis`, `alwaysStrict`. Every one catches real bugs. **Disabling any strict flag to silence a type error is fixing the symptom, not the disease. Fix the type, not the config.**

### Composition Over Inheritance

React uses composition (components rendering other components, hooks extracting reusable logic). Node.js services use composition (dependency injection, middleware chains, plugin systems). TypeScript supports composition through interfaces, generics, and utility types. Deep class hierarchies are rare in modern TypeScript. **When you reach for `extends`, ask whether `implements` or a composable function achieves the same goal with less coupling.**

### Explicit Over Magic

- Explicit imports over barrel re-exports that obscure origin.
- Explicit types on function signatures over inferred types that change when implementation changes.
- Explicit dependency injection over global singletons.
- Explicit error handling over swallowed promises.

The cost of explicitness is a few more characters. The cost of magic is hours of debugging.

### Colocation

Code that changes together lives together. A component's TypeScript, styles, tests, stories, and types colocate in the same directory. A server route's handler, validation schema, and response types colocate. Shared types used by both frontend and backend live in a shared package. **Colocated code is discoverable, maintainable, and deletable as a unit.**

### Foundational Rules

- `strict: true` in `tsconfig.json` is non-negotiable. Additionally enable `noUncheckedIndexedAccess`, `exactOptionalProperties`, and `noUnusedLocals`. These catch real bugs that strict alone misses.
- **Target** `ES2022` or later for Node.js backends (matches Node 22 LTS capabilities). Target `ESNext` for frontend code where the bundler handles downleveling.
- **Module:** `NodeNext` for Node.js projects, `ESNext` or `Bundler` for frontend projects.
- **moduleResolution:** `bundler` for Vite/webpack projects; `nodenext` for pure Node.js projects.

---
[Back to Overview](./OVERVIEW.md)
