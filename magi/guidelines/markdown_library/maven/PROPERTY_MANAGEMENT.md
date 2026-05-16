# Property Management

### Global Properties (Parent POM)

```xml
<properties>
    <!-- Java -->
    <java.version>21</java.version>
    <maven.compiler.source>${java.version}</maven.compiler.source>
    <maven.compiler.target>${java.version}</maven.compiler.target>
    <!-- Encoding -->
    <project.build.sourceEncoding>UTF-8</project.build.sourceEncoding>
    <project.reporting.outputEncoding>UTF-8</project.reporting.outputEncoding>
    <!-- Reproducible builds — byte-identical artifacts -->
    <project.build.outputTimestamp>2026-01-01T00:00:00Z</project.build.outputTimestamp>
    <!-- Plugin versions -->
    <maven.compiler.plugin.version>3.11.0</maven.compiler.plugin.version>
    <maven.surefire.plugin.version>3.1.2</maven.surefire.plugin.version>
    <!-- Dependency versions -->
    <spring.boot.version>3.2.0</spring.boot.version>
    <junit.version>5.10.0</junit.version>
</properties>
```

### Environment-Specific Properties

```xml
<profiles>
    <profile>
        <id>dev</id>
        <properties>
            <database.url>jdbc:h2:mem:testdb</database.url>
            <log.level>DEBUG</log.level>
        </properties>
    </profile>
    <profile>
        <id>prod</id>
        <properties>
            <database.url>jdbc:postgresql://prod-db:5432/appdb</database.url>
            <log.level>INFO</log.level>
        </properties>
    </profile>
</profiles>
```

---
[Back to Overview](./OVERVIEW.md)
