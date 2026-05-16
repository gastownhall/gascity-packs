# Testing

### Test Suite Declaration

Use native test suites for organized test configurations.

```kotlin
testing {
    suites {
        val test by getting(JvmTestSuite::class) {
            useJUnitJupiter(libs.versions.junit)
            dependencies {
                implementation(libs.assertj.core)
            }
        }

        val integrationTest by registering(JvmTestSuite::class) {
            useJUnitJupiter(libs.versions.junit)
            dependencies {
                implementation(project())
                implementation(libs.bundles.testing)
                implementation(libs.testcontainers.junit)
                implementation(libs.testcontainers.postgresql)
            }
            targets {
                all {
                    testTask.configure {
                        shouldRunAfter(test)
                    }
                }
            }
        }
    }
}

tasks.named("check") {
    dependsOn(testing.suites.named("integrationTest"))
}
```

| Constraint | Detail |
|:-----------|:-------|
| JUnit Platform | `useJUnitPlatform()` for JUnit 5; add `junit-platform-launcher` as `testRuntimeOnly` |
| Parallel tests | `maxParallelForks` = half of available processors (balance speed and memory) |
| Ordering | `shouldRunAfter` chains: integration after unit, functional after integration |

### Test Execution Configuration

```kotlin
tasks.withType<Test>().configureEach {
    useJUnitPlatform()
    failFast = providers.environmentVariable("CI").isPresent
    maxParallelForks = (Runtime.getRuntime().availableProcessors() / 2).coerceAtLeast(1)
    testLogging {
        events("passed", "skipped", "failed")
        exceptionFormat = org.gradle.api.tasks.testing.logging.TestExceptionFormat.FULL
    }
    reports {
        html.required.set(true)
        junitXml.required.set(true)
    }
    jvmArgs = listOf("-Xmx2g", "-XX:MaxMetaspaceSize=512m")
}
```

Generate both HTML and JUnit XML reports for CI integration.

---
[Back to Overview](./OVERVIEW.md)
