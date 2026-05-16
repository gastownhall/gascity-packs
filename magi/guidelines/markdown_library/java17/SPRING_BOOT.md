# Spring Boot Integration

### Spring Boot 3.x with Jakarta EE

Spring Boot 2.x is in maintenance mode. Spring Framework 6 and Spring Boot 3 are built for Java 17 and use `jakarta.*` namespace.

### Records as Spring DTOs

```java
public record CreateOrderRequest(
    @NotNull UUID customerId,
    @NotEmpty List<UUID> productIds,
    @Valid ShippingAddress shipping) {}

@PostMapping("/orders")
public ResponseEntity<OrderResponse> create(@Valid @RequestBody CreateOrderRequest request) { ... }
```

Spring Boot 3.x and Jackson 2.12+ support records natively. `@RequestBody` and `@ResponseBody` work with records. Bean Validation annotations work on record components. Use records for `@ConfigurationProperties` with `@ConstructorBinding` (implicit in Spring Boot 3.x for records).

### Constructor Injection Exclusively

```java
@Service
public final class OrderService {
    private final OrderRepository repo;
    private final EventPublisher publisher;

    public OrderService(OrderRepository repo, EventPublisher publisher) {
        this.repo = repo;
        this.publisher = publisher;
    }
}
```

Spring Boot 3.x supports constructor injection with a single constructor without `@Autowired`. **Do not use field injection.** Field injection hides dependencies, prevents immutability, complicates testing, and does not work with `final` fields.

### Native Image (Optional)

Spring Native / GraalVM native image compilation for microservices where startup time matters (serverless, scale-to-zero). Java 17 is the baseline. Native images start in milliseconds and use significantly less memory. Verify all reflection, proxy, and serialization usage is registered with GraalVM's native-image configuration.

---
[Back to Overview](./OVERVIEW.md)
