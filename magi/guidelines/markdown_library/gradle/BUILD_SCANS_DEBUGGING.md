# Build Scans and Debugging

### Build Scan Configuration

```kotlin
// settings.gradle.kts
plugins {
    id("com.gradle.develocity") version "3.18.1"
}

develocity {
    buildScan {
        termsOfUseUrl.set("https://gradle.com/terms-of-service")
        termsOfUseAgree.set("yes")
        publishing.onlyIf { providers.environmentVariable("CI").isPresent }
        obfuscation {
            ipAddresses { addresses -> addresses.map { "0.0.0.0" } }
        }
    }
}
```

Build scans provide timeline analysis, dependency resolution tracing, cache performance metrics, and failure diagnostics.

### Debug Commands

| Command | Purpose |
|:--------|:--------|
| `--debug` | Full debug output |
| `--info` | Informational logging |
| `--stacktrace` | Failure stack traces |
| `dependencyInsight --dependency X --configuration Y` | Trace dependency resolution |
| `--dry-run` | Visualize task execution without running tasks |
| `--configuration-cache-problems=warn` | Diagnose cache compatibility issues |
| `--warning-mode=all` | Surface all deprecation warnings |
| `--scan` | Publish a build scan for the run |

---
[Back to Overview](./OVERVIEW.md)
