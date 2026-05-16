# TypeScript, React, and Node.js Development Library

**Runtime:** TypeScript 5.8+, React 19.2+, Node.js 22 LTS (active) or 24 LTS (current), Yarn 4.x (Berry) via Corepack, Vite 6+ or Next.js 15+ for bundling, Vitest/Jest for testing.

**Scope:** All frontend (React 19 SPA and SSR), backend (Node.js API servers, Nitro, Express, Fastify), and shared library code written in TypeScript. Covers greenfield development and migrations from JavaScript codebases.

## Critical Mandates (Read First)

- **TypeScript Everywhere** — Every file in the stack is TypeScript. A bug caught by `tsc` costs zero runtime; a bug caught in production costs hours.
- **Strict Mode, No Exceptions** — `strict: true` is non-negotiable. Disabling any strict flag to silence a type error is fixing the symptom, not the disease.
- **Composition Over Inheritance** — When you reach for `extends`, ask whether `implements` or a composable function achieves the same goal with less coupling.
- **Explicit Over Magic** — The cost of explicitness is a few more characters; the cost of magic is hours of debugging.
- **Colocation** — Code that changes together lives together. Colocated code is discoverable, maintainable, and deletable as a unit.
- **Shakedown Required** — A §11 shakedown MUST pass after every triggering change before promotion.

## Table of Contents

1. [Core Principles](./CORE_PRINCIPLES.md)
2. [TypeScript Type System](./TYPE_SYSTEM.md)
3. [React 19 Component Architecture](./REACT_COMPONENTS.md)
4. [Hooks Patterns](./HOOKS.md)
5. [State Management](./STATE_MANAGEMENT.md)
6. [Node.js Runtime](./NODEJS_RUNTIME.md)
7. [Yarn 4 Package Management](./YARN.md)
8. [Error Handling](./ERROR_HANDLING.md)
9. [Async Patterns](./ASYNC_PATTERNS.md)
10. [Testing](./TESTING.md)
11. [Shakedown — Integration Validation](./SHAKEDOWN.md)
12. [Linting and Formatting](./LINTING.md)
13. [Security](./SECURITY.md)
14. [Performance](./PERFORMANCE.md)
15. [Project Structure](./PROJECT_STRUCTURE.md)
16. [Defense in Depth](./DEFENSE_IN_DEPTH.md)
17. [Prohibited Practices](./PROHIBITED_PRACTICES.md)
18. [Required Practices](./REQUIRED_PRACTICES.md)
19. [Style Summary](./STYLE_SUMMARY.md)
