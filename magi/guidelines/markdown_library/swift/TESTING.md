# Testing Strategy

### Unit Tests

- Test **public interfaces**; do not test private implementation details.
- One logical assertion per test; multiple related assertions are acceptable if they verify a single behavior.
- Name tests descriptively: `test_login_withInvalidCredentials_returnsAuthenticationError`.
- Use `XCTAssertEqual`, `XCTAssertThrowsError`, and typed assertions; avoid bare `XCTAssert` with boolean expressions.

### Async Testing

- Use `async` test methods for testing async functions directly.
- Use `XCTestExpectation` for callback-based APIs that haven't been modernized.
- Set reasonable timeouts; tests that hang indefinitely indicate a concurrency bug.

### Swift Testing Framework (Swift 6+)

```swift
import Testing

@Suite("User Authentication")
struct AuthenticationTests {
    @Test("Valid credentials return success", .tags(.authentication))
    func validLogin() async throws {
        let result = try await auth.login(username: "user", password: "pass")
        #expect(result == .success)
    }

    @Test(arguments: ["", "a", "ab"])
    func invalidPassword(password: String) async {
        await #expect(throws: ValidationError.self) {
            try await auth.validate(password: password)
        }
    }
}
```

- Use `@Test` instead of XCTest methods.
- Use `@Test` with arguments for parameterized tests.
- Use `#Tag` for test organization.

### Mocking and Dependency Injection

- Define **protocol-based dependencies**; inject implementations via initializers.
- Create mock implementations for tests; **do not reach for heavy mocking frameworks**.
- Use test doubles that return canned data; verify calls with captured arguments when interaction matters.

### Test Organization

- Mirror source structure in test targets: `Sources/Features/Auth/AuthService.swift` → `Tests/UnitTests/Features/Auth/AuthServiceTests.swift`.
- Group related tests in extensions or separate test classes.
- Shared test fixtures live in a `TestSupport/` module importable by test targets.

---
[Back to Overview](./OVERVIEW.md)
