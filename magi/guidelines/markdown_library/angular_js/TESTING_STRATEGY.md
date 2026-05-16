# Testing Strategy

### Test Infrastructure

- **Karma**: Test runner.
- **Jasmine**: Assertion library.
- **`angular-mocks`**: Provides `module()`, `inject()`, and `$httpBackend`.

### Service Testing

Inject through the test module and mock dependencies. Use `$httpBackend` to verify request construction and mock responses.

### Component Testing

Use `$componentController` for unit tests. Use `$compile` and `$rootScope.$digest()` for template interaction tests.

### Directive Testing

Compile host elements with the directive, trigger events, and assert DOM state or callbacks.

### Test Organization

Colocate `.spec.js` files with their source counterparts.

### Coverage Requirements

- **Services / Core logic**: 80%+
- **Component controllers**: 70%+

---
[Back to Overview](./OVERVIEW.md)
