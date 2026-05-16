# Testing

### Test Runner Selection

| Project | Runner |
|:--------|:-------|
| Vite-based | **Vitest** — faster due to shared configuration and native ESM support |
| Non-Vite | Jest |

Both provide TypeScript support, mocking, snapshot testing, coverage. Configure with `tsconfig` paths for consistent module resolution between application and test code.

### React Testing Library — Test Behavior

```typescript
test('submits form and shows success', async () => {
  render(<MyForm />);
  await userEvent.type(screen.getByLabelText(/email/i), 'a@b.co');
  await userEvent.click(screen.getByRole('button', { name: /submit/i }));
  expect(await screen.findByText(/success/i)).toBeInTheDocument();
});
```

- Query by **role, text, label, placeholder** — not by class name, test ID, or component internals.
- A test that clicks a "Submit" button and verifies a success message is a **behavior** test.
- A test that checks `useState` was called with a specific value is an **implementation** test that breaks on refactoring.

### Type Mock Return Values

```typescript
vi.mocked(userService.getById).mockResolvedValue({
  id: '1',
  email: 'a@b.co',
  // Type-checked against User
});
```

`vi.fn().mockReturnValue(value)` and `vi.mocked(module).mockResolvedValue(value)` must return values matching the mocked function's return type. **Untyped mocks that return incorrect shapes pass in tests but would fail in production**, creating false confidence.

### MSW for API Mocking

Use **MSW (Mock Service Worker)** for API mocking in both component tests and integration tests. MSW intercepts network requests at the service worker level, providing realistic API simulation **without modifying application code**. Define handlers once and share across test suites. MSW catches bugs that manual `fetch` mocking misses (incorrect headers, missing error handling, wrong HTTP methods).

### Backend HTTP Tests

Use **supertest** or the framework's built-in test client for HTTP endpoint testing. Test the full request/response cycle: route matching, middleware execution, input validation, handler logic, response formatting. **Mock only external dependencies** (database, third-party APIs), not internal modules.

---
[Back to Overview](./OVERVIEW.md)
