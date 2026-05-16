# API Design

### Program to Interfaces

Method parameters and return types use `List`, `Set`, `Map`, `Collection` — not `ArrayList`, `HashSet`, `HashMap`. Concrete types appear only at the instantiation site.

### Return Empty Collections, Not Null

```java
public List<Order> findOrders(UUID customerId) {
    var rows = jdbc.query(...);
    return rows.isEmpty() ? List.of() : rows;
}
```

Forces no null check on every iteration site. An empty collection iterates zero times naturally.

### Limit Parameter Count

```java
// FORBIDDEN — too many parameters
public Order createOrder(String customerId, String productId, int quantity,
                         String shippingAddress, String billingAddress,
                         String paymentMethodId, String couponCode) { ... }

// CORRECT — record parameter
public Order createOrder(CreateOrderRequest request) { ... }
```

Limit method parameter count to 3–4. More parameters indicate a missing abstraction.

### Builder Pattern for Many Optional Parameters

Records require all components at construction. For configurable objects with 5+ optional fields, provide a builder with sensible defaults. Consider the Step Builder pattern for objects with required parameters that must be set in order.

### Document Public APIs with Javadoc

Every public class, interface, method, and constructor in a library or shared module includes Javadoc describing purpose, `@param`, `@return`, `@throws`, and thread-safety guarantees. Internal implementation classes may rely on clean naming for self-documentation.

---
[Back to Overview](./OVERVIEW.md)
