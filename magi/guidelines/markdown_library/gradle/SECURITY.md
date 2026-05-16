# Security

### Dependency Verification

Enable dependency verification for supply chain security:

```bash
./gradlew --write-verification-metadata sha256,pgp
```

The generated `gradle/verification-metadata.xml` contains checksums and PGP signatures for all dependencies. Commit and maintain this file. Builds fail when dependencies do not match verified checksums.

### Secrets Management

Never hardcode credentials in build scripts. Access credentials via:

```kotlin
val repoUser: String = providers.gradleProperty("internalRepoUser")
    .orElse(providers.environmentVariable("REPO_USER"))
    .get()
```

- Repository credentials, signing keys, and API tokens never commit to version control.
- Sensitive values live in `~/.gradle/gradle.properties` or CI secret stores.
- Fail fast with clear error messages when required credentials are missing.

### Repository Security

- Enforce HTTPS for all repository URLs. Never use HTTP repositories in production builds.
- Internal repositories require authentication.
- Verify repository SSL certificates.
- Use repository content filtering to restrict which dependencies can come from which repositories:

```kotlin
repositories {
    mavenCentral {
        content {
            excludeGroupByRegex("com\\.company\\..*")
        }
    }
    maven("https://nexus.example.com/repository/internal") {
        content {
            includeGroup("com.company")
        }
    }
}
```

---
[Back to Overview](./OVERVIEW.md)
