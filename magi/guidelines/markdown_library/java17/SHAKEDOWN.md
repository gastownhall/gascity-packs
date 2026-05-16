# Shakedown — Integration Validation

### Definition

A Java 17 shakedown is the **first controlled, end-to-end execution of the service under real operating conditions** — Spring `ApplicationContext` fully initialized, bean graph resolved, Flyway/Liquibase migrations applied against a real database, Kafka/RabbitMQ/SQS broker reached, Resilience4j circuit breakers primed, Micrometer metrics flowing.

It is integration validation of the composed system, distinct from JUnit unit tests, JMH micro-benchmarks, and static preflight checks.

### Shakedown vs Preflight vs Testing

| Layer | Question Answered |
|:------|:------------------|
| Preflight | Build succeeds, dependencies resolve, Dockerfile builds, configuration files parse |
| **Shakedown** | **Beans wire, migrations apply, brokers connect, health checks report `Status.UP`** |
| Testing | Behavioral correctness at scale, edge cases, regression coverage |

Shakedown runs after preflight (`mvn verify` succeeds, static analysis passes, images build) and before full behavioral testing or production deployment.

### Two Canonical Forms

1. **Spring Boot `ApplicationRunner` bean** annotated `@Profile("shakedown")` — executes the shakedown sequence after the `ApplicationContext` is fully initialized but before the service accepts traffic. Exits the JVM with a non-zero code on fail-blocking, preventing the embedded Tomcat/Netty listener from binding.
2. **Dedicated JUnit 5 integration test module (`shakedown-it`)** backed by Testcontainers — runs via `mvn verify -Pshakedown` or `gradle shakedownTest` in CI before deployment.

Services use form (1); libraries and shared modules use form (2).

### Mandatory Triggers

Shakedown is mandatory when any of the following occur:

- First deployment of a new service.
- Major refactor of `@Configuration` classes or bean graph.
- Spring Boot major/minor version upgrade.
- JDK upgrade (17 → 21, Temurin → Corretto).
- New Spring Data module added (`jpa`, `mongodb`, `redis`).
- Flyway/Liquibase migration addition.
- Broker version bump (Kafka client, RabbitMQ client).
- Resilience4j configuration change.
- DataSource provider swap (HikariCP → Agroal).
- Move between embedded Tomcat and Netty.
- Repair after a production incident affecting bean wiring or messaging.

### Non-Triggers

- Bug fixes confined to a single class.
- Text or logging changes.
- `@ConfigurationProperties` value tweaks within a validated schema.

### Validation Categories

A Java 17 shakedown validates these integration surfaces explicitly:

1. **Bean graph wiring** — every `@Component`, `@Service`, `@Repository`, `@Configuration` resolves via `ApplicationContext.getBean`; `@Primary` and `@Qualifier` resolve to the expected instance; scoped beans instantiate inside the correct scope; no circular dependency warnings.
2. **Flyway/Liquibase migrations** — the migration runner applies all pending migrations against the real database and reports schema version at the expected baseline.
3. **DataSource connectivity** — HikariCP acquires connections, executes a known-good query, and returns rows deserialized into `@Entity` or record types.
4. **Message broker connectivity** — `KafkaTemplate` publishes a known-good message and the `@KafkaListener` consumer handles it end-to-end; `RabbitTemplate` round-trips a test message; SQS publishes and polls successfully.
5. **Resilience4j circuit breakers** — every `CircuitBreaker`, `Retry`, and `TimeLimiter` registered under `CircuitBreakerRegistry` is in `CLOSED` state and accepts invocations.
6. **`@ConfigurationProperties` binding** — every `@ConfigurationProperties` class binds from `application.yml` or environment variables without binding errors.
7. **Micrometer metric registry** — the `MeterRegistry` receives the expected gauges, counters, timers and exports them to the configured backend.
8. **Side effect correctness** — writes land on the correct table, messages on the correct topic/queue, log events with the correct MDC context.

### Execution Principles

- **Conservative inputs** — representative command payloads with known expected outputs; not JQwik property-based, not Jackson auto-generated fixtures.
- **Progressive stress** — single request through the happy path via `MockMvc` or `WebTestClient`, then concurrency via `CompletableFuture.allOf` only after the sequential path passes.
- **Controlled environment** — Testcontainers for every external dependency with **pinned image digests**.
- **Observable execution** — Logback at DEBUG for shakedown packages, Micrometer tracing enabled with the logging exporter, every span captured.
- **Known-good inputs** — committed alongside the shakedown module.
- **No optimization** — do not tune HikariCP pool size, Kafka batch size, or JVM flags during shakedown. Log observations and move on.

### Execution Sequence

| Step | Action |
|:----:|:-------|
| 1 | Confirm preflight: `mvn verify` with `-Werror`, SpotBugs, Checkstyle all green |
| 2 | Start Testcontainers for every real dependency; await readiness via wait strategies |
| 3 | Bring up `ApplicationContext` with the real composition root pointed at Testcontainer endpoints via `@DynamicPropertySource` |
| 4 | Resolve every bean via `ApplicationContext.getBeansOfType` for critical interfaces |
| 5 | Verify Flyway/Liquibase migrations applied (`schema_version` or `DATABASECHANGELOG`) |
| 6 | Execute a known-good repository query; assert row shape |
| 7 | Publish a known-good message; assert listener handled it within bound |
| 8 | Query every `HealthIndicator`; assert `Status.UP` |
| 9 | Verify Micrometer captured the expected meters |
| 10 | Shut down the context; dispose Testcontainers; assert no connection leaks (`HikariPoolMXBean` reports zero active), no thread leaks (`ThreadMXBean` snapshot matches baseline) |
| 11 | Record observations as structured JSON; classify the run |

### Result Classification

- **PASS** — ready for testing and deployment.
- **FAIL_BLOCKING** — integration fault prevents operation. Fix code; re-run from step 1.
- **FAIL_NON_BLOCKING** — observed anomaly that does not prevent operation; requires an issue ticket with full diagnostic context.
- **INCONCLUSIVE** — environment or input limitation prevented validation; adjust the specific validation and re-run it.

The classification is written to `shakedown-result.json` alongside the execution log.

### Required Artifacts

Stored under a project-local scratch directory (`target/shakedown/`, `build/shakedown/`, `.scratch/shakedown/`) — **never `/tmp`, never `java.io.tmpdir`, never any directory named `tmp`**:

- **Execution log** — full Logback output with MDC fields, timestamps, correlation IDs, captured via a `FileAppender` configured for shakedown.
- **Result summary** — classification per validation category as JSON.
- **Issue list** — every anomaly classified blocking/non-blocking/deferred with reproduction context.
- **Environment snapshot** — `java --version` output, Maven/Gradle dependency tree hash, Testcontainers image digests, `@ConfigurationProperties` values with secrets redacted.

The shakedown run is not complete until every artifact is persisted.

### Anti-Patterns (Forbidden)

- Skipping shakedown after a "small" `@Configuration` refactor that touches bean wiring.
- Packing dozens of assertions into the shakedown runner; treating it as a replacement for the integration test suite.
- Running shakedown against `@MockBean`, H2 in-memory database, or embedded Kafka instead of Testcontainers images that match production.
- Tuning HikariCP, JVM flags, Kafka producer settings, or GC options during shakedown.
- Swallowing exceptions in the `ApplicationRunner` instead of classifying them.
- Running shakedown without persisting artifacts.
- Writing artifacts to `/tmp`, `java.io.tmpdir`, or any system temp directory.

### Reference ApplicationRunner

```java
package com.example.shakedown;

import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Duration;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.Objects;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.SerializationFeature;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.boot.actuate.health.HealthEndpoint;
import org.springframework.boot.actuate.health.Status;
import org.springframework.context.annotation.Profile;
import org.springframework.core.env.Environment;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;

/// Sealed classification for every shakedown observation.
public sealed interface ShakedownOutcome
    permits ShakedownOutcome.Pass, ShakedownOutcome.FailBlocking,
            ShakedownOutcome.FailNonBlocking, ShakedownOutcome.Inconclusive {
    record Pass() implements ShakedownOutcome {}
    record FailBlocking(String reason) implements ShakedownOutcome {}
    record FailNonBlocking(String reason) implements ShakedownOutcome {}
    record Inconclusive(String reason) implements ShakedownOutcome {}
}

/// A single observation recorded by the shakedown runner.
public record ShakedownObservation(String category, ShakedownOutcome outcome, long durationMillis) {
    public ShakedownObservation {
        Objects.requireNonNull(category, "category");
        Objects.requireNonNull(outcome, "outcome");
    }
}

/// Runs the startup shakedown for the composed Spring Boot service.
@Component
@Profile("shakedown")
public final class StartupShakedownRunner implements ApplicationRunner {

    private static final Logger LOG = LoggerFactory.getLogger(StartupShakedownRunner.class);

    private final JdbcTemplate jdbcTemplate;
    private final HealthEndpoint healthEndpoint;
    private final Environment environment;
    private final ObjectMapper objectMapper;

    public StartupShakedownRunner(JdbcTemplate jdbcTemplate, HealthEndpoint healthEndpoint, Environment environment) {
        this.jdbcTemplate = Objects.requireNonNull(jdbcTemplate, "jdbcTemplate");
        this.healthEndpoint = Objects.requireNonNull(healthEndpoint, "healthEndpoint");
        this.environment = Objects.requireNonNull(environment, "environment");
        this.objectMapper = new ObjectMapper().enable(SerializationFeature.INDENT_OUTPUT);
    }

    @Override
    public void run(ApplicationArguments args) throws Exception {
        LOG.info("Shakedown starting");
        List<ShakedownObservation> observations = new ArrayList<>();
        observations.add(validateDatabase());
        observations.add(validateHealth());
        Path artifactsDirectory = Path.of(environment.getProperty("shakedown.artifacts", "build/shakedown"));
        Files.createDirectories(artifactsDirectory);
        Path summaryPath = artifactsDirectory.resolve("shakedown-summary.json");
        Files.writeString(summaryPath, objectMapper.writeValueAsString(observations));
        LOG.info("Shakedown summary written to {}", summaryPath);
        ShakedownOutcome worst = worstOutcome(observations);
        switch (worst) {
            case ShakedownOutcome.Pass ignored -> LOG.info("Shakedown PASS");
            case ShakedownOutcome.FailNonBlocking fnb -> LOG.warn("Shakedown FAIL_NON_BLOCKING: {}", fnb.reason());
            case ShakedownOutcome.Inconclusive inc -> LOG.warn("Shakedown INCONCLUSIVE: {}", inc.reason());
            case ShakedownOutcome.FailBlocking fb -> {
                LOG.error("Shakedown FAIL_BLOCKING: {}", fb.reason());
                throw new IllegalStateException("Shakedown fail-blocking: " + fb.reason());
            }
        }
    }

    private ShakedownObservation validateDatabase() {
        Instant started = Instant.now();
        try {
            Integer result = jdbcTemplate.queryForObject("SELECT 1", Integer.class);
            if (result == null || result != 1) {
                return new ShakedownObservation("data-flow-integrity",
                    new ShakedownOutcome.FailBlocking("unexpected probe result"),
                    Duration.between(started, Instant.now()).toMillis());
            }
            return new ShakedownObservation("data-flow-integrity",
                new ShakedownOutcome.Pass(),
                Duration.between(started, Instant.now()).toMillis());
        } catch (RuntimeException ex) {
            return new ShakedownObservation("data-flow-integrity",
                new ShakedownOutcome.FailBlocking(ex.getMessage()),
                Duration.between(started, Instant.now()).toMillis());
        }
    }

    private ShakedownObservation validateHealth() {
        Instant started = Instant.now();
        Status status = healthEndpoint.health().getStatus();
        long elapsed = Duration.between(started, Instant.now()).toMillis();
        if (Status.UP.equals(status)) {
            return new ShakedownObservation("health-checks", new ShakedownOutcome.Pass(), elapsed);
        }
        return new ShakedownObservation("health-checks",
            new ShakedownOutcome.FailBlocking("health status " + status.getCode()), elapsed);
    }

    private static ShakedownOutcome worstOutcome(List<ShakedownObservation> observations) {
        ShakedownOutcome worst = new ShakedownOutcome.Pass();
        for (ShakedownObservation observation : observations) {
            worst = switch (observation.outcome()) {
                case ShakedownOutcome.FailBlocking fb -> fb;
                case ShakedownOutcome.FailNonBlocking fnb -> worst instanceof ShakedownOutcome.FailBlocking ? worst : fnb;
                case ShakedownOutcome.Inconclusive inc -> worst instanceof ShakedownOutcome.Pass ? inc : worst;
                case ShakedownOutcome.Pass pass -> worst;
            };
        }
        return worst;
    }
}
```

---
[Back to Overview](./OVERVIEW.md)
