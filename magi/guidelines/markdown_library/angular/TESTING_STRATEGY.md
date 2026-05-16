# Testing Strategy

### Test Pyramid

- **Unit tests** (70%): Services, pipes, guards, resolvers. Fast, high coverage, mock dependencies.
- **Component tests** (20%): Behavior through DOM with `TestBed` or Angular Testing Library. Mock services and HTTP.
- **End-to-end tests** (10%): Full application user flows with Playwright or Cypress.

### Service Testing

Test services without `TestBed` if they have no Angular dependencies. Use `TestBed` for services using `HttpClient` or the router.

### Component Testing

Use Angular Testing Library to prioritize user behavior:
- Query by role/label/text.
- Simulate interactions (click, type).
- Assert visible outcomes and output emissions.
- Test loading/error/success states.

### Signal Testing

Test signal-based state by reading values directly. Signals are synchronous—no need for complex async utilities.

```typescript
it('should calculate total from items', () => {
    const service = TestBed.inject(CartService);
    service.addItem({ price: 10, quantity: 2 });
    expect(service.total()).toBe(20);
});
```

### HTTP Testing

Use `HttpTestingController` to intercept and mock requests:
- Assert correct URL, method, and headers.
- Flush responses for success and error paths.
- Call `httpMock.verify()` in `afterEach`.

### Code Coverage

Enforce minimum 80% line and branch coverage in CI. Target 90%+ for core services and shared utilities.

---
[Back to Overview](./OVERVIEW.md)
