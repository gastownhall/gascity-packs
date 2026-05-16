# Testing

### JUnit 5 (Jupiter) for All New Tests

JUnit 4 is legacy. JUnit 5 provides `@ParameterizedTest`, `@Nested`, `@DisplayName`, `@TempDir`, `assertThrows`, and extension points.

### Test Behavior, Not Implementation

Test the public API contract of each class. **Do not test private methods directly** — they are tested indirectly through public method behavior. Tests that mirror the implementation structure break on every refactoring.

### AssertJ for Fluent Assertions

```java
assertThat(result)
    .isNotNull()
    .hasSize(3)
    .extracting(Order::status)
    .containsExactly(Status.PLACED, Status.SHIPPED, Status.DELIVERED);
```

Prefer AssertJ over JUnit's built-in assertions for complex assertions on collections, maps, exceptions, and strings.

### Mockito for Test Doubles

Mock external dependencies (repositories, HTTP clients, message producers). **Do not mock the class under test. Do not mock value objects or records.** Use `verify()` only when interaction is the behavior being tested (e.g., verifying a message was published), not as a substitute for asserting output values.

### Parameterized Tests

```java
@ParameterizedTest
@CsvSource({
    "0,        ZERO",
    "1,        ONE",
    "10,       TEN",
    "1000000,  MILLION"
})
void categorizesAmount(long input, String expected) {
    assertThat(Categorizer.of(input)).isEqualTo(Category.valueOf(expected));
}
```

A single parameterized test covering 10 inputs replaces 10 copy-pasted test methods.

### Given-When-Then Structure

```java
@Test
void rejectsExpiredCard() {
    // Given
    var card = new CreditCard("4242", YearMonth.of(2020, 1));
    var clock = Clock.fixed(Instant.parse("2024-06-01T00:00:00Z"), UTC);
    var validator = new CardValidator(clock);

    // When
    var result = validator.validate(card);

    // Then
    assertThat(result).isEqualTo(ValidationResult.EXPIRED);
}
```

Each test method tests one behavior. Multiple unrelated assertions = multiple behaviors → split.

---
[Back to Overview](./OVERVIEW.md)
