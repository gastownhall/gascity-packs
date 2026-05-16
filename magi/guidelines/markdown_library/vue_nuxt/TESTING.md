# Testing

### Unit and Component Testing

Use Vitest as the test runner (integrated with Nuxt via `@nuxt/test-utils`). Use `@vue/test-utils` for component mounting. Test components in isolation with mocked dependencies. Use `nuxt/test-utils` helpers (`mountSuspended`, `renderSuspended`) for components that use Nuxt composables (`useFetch`, `useRoute`, `useState`). Mock `$fetch` and API responses via `vi.mock` or msw (Mock Service Worker). Test composables independently by calling them within a Vue test component or using a test Pinia instance for store-dependent composables.

### End-to-End Testing

Use Playwright or Cypress for E2E tests. Test critical user flows: authentication, checkout, form submissions, navigation. **Run E2E tests against a production-like build (`nuxt build` + `nuxt preview`)** to verify SSR behavior, hydration, and server routes. E2E tests catch integration issues that unit tests miss: hydration mismatches, broken API contracts, missing middleware redirects. Run E2E in CI on every PR targeting `main`.

---
[Back to Overview](./OVERVIEW.md)
