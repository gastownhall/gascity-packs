# Testing

Testing React + TypeScript applications covers unit tests (hooks, utilities), component tests (rendering, interaction, accessibility), and integration tests (page-level flows). TypeScript ensures test code has the same type safety as production code.

### Test Stack

| Tool | Use |
|:-----|:----|
| **Vitest** (preferred for Vite) or **Jest** | Test runner |
| **React Testing Library** (`@testing-library/react`) | Component testing |

Testing Library enforces testing from the user's perspective: query by accessible role, text, label — not by CSS selector, component internals, or implementation details. **Do not use Enzyme** — it is incompatible with React 18+ and encourages shallow rendering that misses integration bugs.

### Test Behavior, Not Implementation

- Click the submit button and assert the form submitted — do **not** assert that `setState` was called with specific arguments.
- Verify visible output (rendered text, navigation, API calls) and accessible state (aria attributes, focus) — do **not** assert internal component state.

Implementation-coupled tests break on every refactor and provide false confidence.

### API Mocking with MSW

Mock API calls with **MSW (Mock Service Worker)** instead of mocking `fetch`/`axios` directly. MSW intercepts network requests at the service worker level, providing realistic mock responses that work identically in tests, development, and Storybook. Define request handlers that match the API contract. Assert that the UI correctly handles success, error, loading, and empty-data responses.

### Custom Hook Tests

Test custom hooks independently with `renderHook` from `@testing-library/react`:

- Assert the hook's return values and state transitions.
- For hooks that call APIs, use MSW for mock responses.
- For hooks with timers, use fake timers (`vi.useFakeTimers` / `jest.useFakeTimers`).
- Test the hook's cleanup by unmounting and verifying resources are released.

### Accessibility Checks in Tests

Run accessibility checks in tests. Use `@testing-library/jest-dom` matchers (`toBeInTheDocument`, `toHaveAccessibleName`) and axe-core integration (`jest-axe` or `vitest-axe`) to assert that rendered components pass automated accessibility checks. **This catches 30–50% of accessibility issues automatically.**

---
[Back to Overview](./OVERVIEW.md)
