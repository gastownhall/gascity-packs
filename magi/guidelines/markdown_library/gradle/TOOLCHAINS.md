# Toolchains

### Java Toolchain Configuration

Declare required Java version via toolchains; Gradle provisions or locates appropriate JDK. Toolchains decouple build JDK from compilation target. The build can run on Java 17 while compiling for Java 21 — Gradle handles JDK resolution.

```kotlin
java {
    toolchain {
        languageVersion.set(JavaLanguageVersion.of(21))
        vendor.set(JvmVendorSpec.ADOPTIUM)
    }
}
```

```kotlin
// settings.gradle.kts
plugins {
    id("org.gradle.toolchains.foojay-resolver-convention") version "0.8.0"
}
```

The foojay-resolver plugin enables automatic JDK download.

### Kotlin Toolchain Integration

Kotlin plugin respects Java toolchain configuration:

```kotlin
kotlin {
    jvmToolchain(21)
}
```

Or the full toolchain DSL for vendor specification. Kotlin and Java compilation use the same toolchain when configured via the Java toolchain DSL.

---
[Back to Overview](./OVERVIEW.md)
