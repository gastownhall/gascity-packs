# Dependency Injection

### Spring Integration

Add `wicket-spring` dependency. Configure `SpringComponentInjector` in `Application.init()`. Use `@SpringBean` annotation to inject services into components. **Spring beans inject as serializable proxies safe for page serialization.**

### CDI Integration

For Jakarta EE environments, configure `CdiConfiguration` with `BeanManager`. Use standard `@Inject` annotation for bean injection. CDI beans receive proper proxy handling for serialization.

**Never instantiate services directly in components.** Use `@SpringBean`, `@Inject`, or equivalent DI mechanism. Direct instantiation breaks testability, creates tight coupling, and fails serialization.

---
[Back to Overview](./OVERVIEW.md)
