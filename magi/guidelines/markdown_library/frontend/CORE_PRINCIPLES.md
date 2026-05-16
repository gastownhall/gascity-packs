# Core Principles

These guidelines define production-grade React/TypeScript single-page applications optimized for:

- **Type Safety**: Strict TypeScript with zero `any` types, comprehensive compile-time validation.
- **Single Source of Truth**: Centralized theme, configuration, and shared state.
- **Performance**: Optimized bundle size, lazy loading, minimal re-renders.
- **Maintainability**: Clear separation of concerns, predictable patterns, testable architecture.
- **Quality Gates**: Zero errors, zero warnings, 90%+ test coverage, Lighthouse 90+ scores.

### Primary Rule: Production-Ready or Nothing

Every line of code must meet production standards from the start. No placeholders, no TODOs, no warnings suppressed, no `any` types. Ship-ready quality is non-negotiable.

### Type Safety Enforcement

Minimum TypeScript version: **5.6.0**. `strict: true` is mandatory.

Forbidden:
```typescript
const data: any = fetchData()
function process(input: any): any { }
type Config = { [key: string]: any }
```

Correct:
```typescript
const data: unknown = fetchData()
function process<T>(input: T): ProcessedResult<T> { }
type Config = Record<string, string | number | boolean>

// For truly dynamic external data
const externalData = JSON.parse(jsonString) as unknown
if (isValidData(externalData)) {
  // externalData is now typed
}
```

---
[Back to Overview](./OVERVIEW.md)
