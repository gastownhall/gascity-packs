# Build Pipeline and Quality Gates

### Build Commands

```json
{
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "preview": "vite preview",
    "test": "vitest",
    "test:coverage": "vitest --coverage",
    "test:e2e": "playwright test",
    "lint": "eslint . --ext ts,tsx",
    "lint:fix": "eslint . --ext ts,tsx --fix",
    "type-check": "tsc --noEmit",
    "format": "prettier --write \"src/**/*.{ts,tsx,css}\"",
    "format:check": "prettier --check \"src/**/*.{ts,tsx,css}\""
  }
}
```

### Quality Gates

Production builds must pass all gates:

1. TypeScript compilation with **zero errors**.
2. ESLint with **zero warnings**.
3. Prettier formatting check passed.
4. Vitest unit tests with **90%+ coverage**.
5. Playwright E2E tests passing.
6. Lighthouse performance score **90+**.
7. Lighthouse accessibility score **90+**.
8. Bundle size under acceptable threshold (initial ≤ 100KB, per-chunk ≤ 200KB).

### Pre-commit Hook

```bash
npx lint-staged
```

```json
{
  "lint-staged": {
    "*.{ts,tsx}": ["eslint --fix", "prettier --write"],
    "*.{json,css,md}": ["prettier --write"]
  }
}
```

---
[Back to Overview](./OVERVIEW.md)
