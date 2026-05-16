# TypeScript and React Development Library

**Runtime:** TypeScript 5.3+, React 18.2+ (React 19 where adopted), Node 20 LTS+, Yarn 1.22 or migration path to Yarn 4 / pnpm / npm 10.

**Node 16 status — read this first.** Node 16 reached End of Life on **September 11, 2023** and no longer receives security patches. Production systems on Node 16 are running on an unsupported, unpatched runtime. Migrate to **Node 20 LTS** (supported through April 2026) or **Node 22 LTS** (supported through April 2027) immediately. This document describes patterns for the current ecosystem; Node 16-specific constraints are called out where they diverge.

## Critical Mandates (Read First)
- **TypeScript Is Not Optional** — every file is `.ts` or `.tsx`.
- **Strict Mode, Always** — `strict: true` plus `noUncheckedIndexedAccess`/`exactOptionalProperties`/`noImplicitOverride`.
- **Components Are Functions** — no class components in new code.
- **Type the Boundaries** — explicit types on props, hook returns, API responses.

## Table of Contents

1. [Core Principles](./CORE_PRINCIPLES.md)
2. [TypeScript Compiler Configuration](./TSCONFIG.md)
3. [Type System Discipline](./TYPE_SYSTEM.md)
4. [React Component Patterns](./COMPONENT_PATTERNS.md)
5. [Hooks](./HOOKS.md)
6. [State Management](./STATE_MANAGEMENT.md)
7. [Data Fetching](./DATA_FETCHING.md)
8. [Forms](./FORMS.md)
9. [Error Handling](./ERROR_HANDLING.md)
10. [Performance](./PERFORMANCE.md)
11. [Accessibility](./ACCESSIBILITY.md)
12. [Testing](./TESTING.md)
13. [Shakedown — Integration Validation](./SHAKEDOWN.md)
14. [Security](./SECURITY.md)
15. [Build and Tooling](./BUILD_TOOLING.md)
16. [Project Structure](./PROJECT_STRUCTURE.md)
17. [Defense in Depth](./DEFENSE_IN_DEPTH.md)
18. [Prohibited Practices](./PROHIBITED_PRACTICES.md)
19. [Required Practices](./REQUIRED_PRACTICES.md)
20. [Style Summary](./STYLE_SUMMARY.md)
