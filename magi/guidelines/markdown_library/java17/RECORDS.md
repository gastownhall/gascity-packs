# Records

Records (JEP 395) are transparent, immutable data carriers that eliminate the boilerplate of constructors, getters, `equals`, `hashCode`, and `toString`.

### Use Records for All Data Carrier Classes

DTOs, API request/response bodies, query results, event payloads, configuration snapshots, value objects.

```java
public record Money(BigDecimal amount, Currency currency) {
    public Money {
        Objects.requireNonNull(amount, "amount");
        Objects.requireNonNull(currency, "currency");
        if (amount.scale() > currency.getDefaultFractionDigits()) {
            throw new IllegalArgumentException("amount scale exceeds currency precision");
        }
    }

    public static Money zero(Currency currency) {
        return new Money(BigDecimal.ZERO, currency);
    }
}
```

### Compact Constructor Validation

Records are immutable after construction — the constructor is the only opportunity to enforce invariants. Use `Objects.requireNonNull` for non-null components and throw `IllegalArgumentException` for domain constraint violations.

### Records Are Implicitly Final

They cannot be extended. They can implement interfaces but cannot extend classes. Design hierarchies via sealed interfaces with record implementations — that combination provides sum types (algebraic data types) the compiler can exhaustively check.

### Do Not Add Mutable State to Records

Records can declare instance methods and static methods, but adding mutable fields defeats their immutability contract. If the data structure needs mutable state, it is not a record — use a standard class with a builder.

### Do Not Override Equals/HashCode on Records

Records generate canonical `equals`/`hashCode` based on all components. Overriding breaks the structural-equality contract that consumers expect.

### Serialization Compatibility

For records used with Jackson 2.12+, native record support handles JSON deserialization. Use `@JsonProperty` on components when JSON field name differs from component name. For frameworks requiring a no-arg constructor, records are not compatible — use a standard class with `@JsonCreator` or upgrade the framework.

---
[Back to Overview](./OVERVIEW.md)
