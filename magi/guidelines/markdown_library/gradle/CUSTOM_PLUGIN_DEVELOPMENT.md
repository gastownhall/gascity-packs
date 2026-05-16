# Custom Plugin Development

### Plugin Project Structure

```kotlin
// build.gradle.kts
plugins {
    `kotlin-dsl`
    `java-gradle-plugin`
}

gradlePlugin {
    plugins {
        create("companyJavaConventions") {
            id = "com.company.java-conventions"
            implementationClass = "com.company.gradle.JavaConventionsPlugin"
        }
    }
}
```

Plugins implement `Plugin<Project>`. Extensions provide configuration DSL. Register tasks in `apply()` using lazy registration.

### Plugin Implementation

```kotlin
// src/main/kotlin/com/company/gradle/JavaConventionsPlugin.kt
abstract class JavaConventionsExtension {
    abstract val javaVersion: Property<Int>
    abstract val coverageThreshold: Property<Double>
}

class JavaConventionsPlugin : Plugin<Project> {
    override fun apply(target: Project) {
        val ext = target.extensions.create<JavaConventionsExtension>("javaConventions").apply {
            javaVersion.convention(21)
            coverageThreshold.convention(0.80)
        }

        target.plugins.apply("java-library")
        target.plugins.apply("jacoco")

        target.extensions.configure<JavaPluginExtension> {
            toolchain {
                languageVersion.set(ext.javaVersion.map(JavaLanguageVersion::of))
            }
        }

        target.tasks.register<VerifyCoverageTask>("verifyCoverage") {
            threshold.set(ext.coverageThreshold)
        }
    }
}
```

- Use abstract classes with Property API for extension properties — Gradle provides implementations.
- Set sensible convention values.
- Wire task configuration to extension properties via providers.
- Tasks must be configurable without extension access for testing.

### Plugin Testing with TestKit

```kotlin
class JavaConventionsPluginTest {

    @TempDir lateinit var projectDir: Path

    @Test
    fun `applies java-library plugin and configures toolchain`() {
        projectDir.resolve("settings.gradle.kts").writeText("""
            rootProject.name = "test-project"
        """.trimIndent())

        projectDir.resolve("build.gradle.kts").writeText("""
            plugins {
                id("com.company.java-conventions")
            }
            javaConventions {
                javaVersion.set(21)
            }
        """.trimIndent())

        val result = GradleRunner.create()
            .withProjectDir(projectDir.toFile())
            .withArguments("verifyCoverage", "--info")
            .withPluginClasspath()
            .build()

        assertThat(result.task(":verifyCoverage")?.outcome).isIn(SUCCESS, UP_TO_DATE)
    }
}
```

Test success paths, failure paths, and configuration variations.

---
[Back to Overview](./OVERVIEW.md)
