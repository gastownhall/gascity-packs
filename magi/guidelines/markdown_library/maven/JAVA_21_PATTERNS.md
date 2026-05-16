# Java 21+ Patterns

### Records for DTOs and Value Objects

```java
public record UserDto(
    String id,
    String username,
    String email,
    Instant createdAt
) {
    // Compact constructor for validation
    public UserDto {
        Objects.requireNonNull(id, "ID cannot be null");
        Objects.requireNonNull(username, "Username cannot be null");
        Objects.requireNonNull(email, "Email cannot be null");
    }
    // Static factory method
    public static UserDto fromEntity(User user) {
        return new UserDto(
            user.getId(),
            user.getUsername(),
            user.getEmail(),
            user.getCreatedAt()
        );
    }
}
```

### Sealed Classes for Domain Modeling

```java
public sealed interface PaymentMethod
    permits CreditCard, DebitCard, PayPal, BankTransfer {
    Money processPayment(Money amount);
}

public record CreditCard(String number, String cvv) implements PaymentMethod {
    public Money processPayment(Money amount) {
        // Credit card processing logic
        return amount;
    }
}

public record PayPal(String email) implements PaymentMethod {
    public Money processPayment(Money amount) {
        // PayPal processing logic
        return amount;
    }
}
```

### Pattern Matching with Switch Expressions

```java
public String formatValue(Object obj) {
    return switch (obj) {
        case Integer i -> String.format("int %d", i);
        case Long l    -> String.format("long %d", l);
        case Double d  -> String.format("double %f", d);
        case String s  -> String.format("String %s", s);
        case null      -> "null";
        default        -> obj.toString();
    };
}

public void processPayment(PaymentMethod method) {
    switch (method) {
        case CreditCard(var number, var cvv) -> {
            // Process credit card with destructured values
        }
        case PayPal(var email) -> {
            // Process PayPal with email
        }
        case BankTransfer transfer -> {
            // Process bank transfer
        }
    }
}
```

### Virtual Threads

```java
@Configuration
@EnableAsync
public class AsyncConfig {
    @Bean
    public TaskExecutor virtualThreadExecutor() {
        return new TaskExecutor() {
            private final ExecutorService executor = Executors.newVirtualThreadPerTaskExecutor();
            @Override
            public void execute(Runnable task) {
                executor.execute(task);
            }
        };
    }
}

// Usage in service
@Service
public class DataService {
    public List<Data> fetchDataConcurrently(List<String> ids) {
        try (var executor = Executors.newVirtualThreadPerTaskExecutor()) {
            List<Future<Data>> futures = ids.stream()
                .map(id -> executor.submit(() -> fetchData(id)))
                .toList();
            return futures.stream()
                .map(future -> {
                    try {
                        return future.get();
                    } catch (Exception e) {
                        throw new RuntimeException(e);
                    }
                })
                .toList();
        }
    }
}
```

---
[Back to Overview](./OVERVIEW.md)
