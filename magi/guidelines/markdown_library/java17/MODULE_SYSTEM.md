# Module System (JPMS)

### module-info.java for Libraries

```java
module com.acme.payment {
    requires java.sql;
    requires com.fasterxml.jackson.databind;

    exports com.acme.payment.api;
    exports com.acme.payment.method;
    // internal packages NOT exported
}
```

Export only the public API packages. Require only the modules the library depends on. Prevents consumers from depending on internal implementation packages and documents the dependency graph explicitly.

For applications (not libraries), `module-info` is optional — the unnamed module (classpath) works for most application deployments.

### --add-opens / --add-exports Restraint

Do not use these flags in production JVM arguments unless migrating from a pre-Java 17 codebase with a documented migration plan. Each usage must be tracked, justified, and targeted for removal. Frameworks (Spring, Hibernate) that required `--add-opens` in early Java 17 adoption typically resolve this in current versions.

### JPMS in Multi-Module Projects

For Maven multi-module / Gradle multi-project builds, use JPMS modules to enforce inter-module dependency boundaries at compile time. A service module that accidentally imports a web controller class from the API module is caught by the module system, not by code review.

---
[Back to Overview](./OVERVIEW.md)
