# Sealed Classes and Interfaces

Sealed classes and interfaces (JEP 409, finalized in Java 17) restrict which classes or interfaces may extend or implement them. Combined with records, they provide algebraic data types: a sealed interface defines a fixed set of variants, and the compiler verifies exhaustive handling in switch expressions.

### Use Sealed Interfaces for Fixed Variant Sets

```java
public sealed interface PaymentMethod
    permits PaymentMethod.CreditCard,
            PaymentMethod.BankTransfer,
            PaymentMethod.Wallet {

    record CreditCard(String last4, YearMonth expiry)         implements PaymentMethod {}
    record BankTransfer(String iban, String bic)              implements PaymentMethod {}
    record Wallet(String provider, String accountId)          implements PaymentMethod {}
}
```

The `permits` clause explicitly declares the complete set of subtypes. The compiler flags any switch that does not handle all permitted types.

### Subclass Modifier Rules

Every direct subclass of a sealed type must be declared:

| Modifier | Use |
|:---------|:----|
| `final` | Leaf types — no further extension. **Most common.** |
| `sealed` | Intermediate types in deep hierarchies — controls its own subclass set |
| `non-sealed` | Opens the hierarchy at that point — only when design intentionally permits unbounded extension |

Prefer `final` for tight domain models.

### Combine Sealed Interfaces with Records

```java
public sealed interface Shape permits Shape.Circle, Shape.Rectangle, Shape.Triangle {
    record Circle(double radius)                              implements Shape {}
    record Rectangle(double width, double height)             implements Shape {}
    record Triangle(double a, double b, double c)             implements Shape {}
}
```

Sum type (sealed interface) + product types (records) = precise domain modeling with zero boilerplate.

### Same Package Requirement

Sealed types and their permitted subtypes must reside in the same package (or the same module if using JPMS). Organize sealed hierarchies in a dedicated package per domain concept (e.g., `com.acme.payment.method`).

### Prefer Sealed Interfaces Over Sealed Abstract Classes

Interfaces allow records to implement them (records cannot extend classes). Sealed abstract classes are justified only when shared mutable state or constructor logic must be inherited by subtypes — rare in immutability-first designs.

---
[Back to Overview](./OVERVIEW.md)
