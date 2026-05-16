# Build and Dependency Management

### Pin All Dependency Versions

No version ranges. Use a BOM (Bill of Materials) for coordinated dependency sets: `spring-boot-dependencies`, `jackson-bom`, `junit-bom`. BOMs ensure compatible versions across related libraries. Use Maven's `dependencyManagement` or Gradle's `platform()` for BOM imports.

### Vulnerability Scanning in CI

OWASP Dependency Check plugin, Snyk, Dependabot. Fail the build on critical/high severity vulnerabilities. Exclude false positives with documented suppressions, not by disabling the scanner. Review and update suppressions quarterly.

### Compiler Warnings as Errors

```xml
<!-- Maven -->
<plugin>
  <artifactId>maven-compiler-plugin</artifactId>
  <configuration>
    <release>17</release>
    <compilerArgs>
      <arg>-Xlint:all</arg>
      <arg>-Werror</arg>
    </compilerArgs>
  </configuration>
</plugin>
```

```kotlin
// Gradle
tasks.withType<JavaCompile> {
    options.compilerArgs.addAll(listOf("-Xlint:all", "-Werror"))
}
```

Warnings that are not errors today become bugs tomorrow.

### Maven Enforcer / Gradle Equivalent

Enforce build invariants: minimum Java version, no SNAPSHOT dependencies in release builds, banned duplicate classes, required plugins.

### Reproducible Builds

Pin plugin versions, use lockfiles (Gradle dependency locking, Maven `dependency:resolve`), avoid build-time network fetches for resources other than declared dependencies.

---
[Back to Overview](./OVERVIEW.md)
