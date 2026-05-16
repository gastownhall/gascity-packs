# Dependency Injection

### Spring Integration

Add the `wicket-spring` dependency. Configure `SpringComponentInjector` in `Application.init()`. Use `@SpringBean` to inject services into components. Spring beans inject as serializable proxies safe for page serialization:

```java
public class OrderPanel extends Panel {

    @SpringBean
    private OrderService orderService;

    @SpringBean
    private NotificationService notificationService;
}
```

### CDI Integration

For Jakarta EE environments, configure `CdiConfiguration` with `BeanManager`. Use standard `@Inject` for bean injection. CDI beans receive proper proxy handling for serialization.

### No Direct Instantiation

**Never instantiate services directly in components.** Use `@SpringBean`, `@Inject`, or equivalent DI mechanism. Direct instantiation breaks testability, creates tight coupling, and fails serialization (services are typically not serializable).

---
[Back to Overview](./OVERVIEW.md)
