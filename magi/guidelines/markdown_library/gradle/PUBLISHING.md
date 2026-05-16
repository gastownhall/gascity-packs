# Publishing

### Maven Publishing Configuration

```kotlin
plugins {
    `java-library`
    `maven-publish`
    signing
}

java {
    withSourcesJar()
    withJavadocJar()
}

publishing {
    publications {
        create<MavenPublication>("maven") {
            from(components["java"])
            pom {
                name.set("Shared Domain")
                description.set("Cross-cutting domain types for the platform")
                url.set("https://example.com/projects/shared-domain")
                licenses {
                    license {
                        name.set("Apache-2.0")
                        url.set("https://www.apache.org/licenses/LICENSE-2.0.txt")
                    }
                }
                developers {
                    developer {
                        id.set("platform-team")
                        name.set("Platform Team")
                        email.set("platform@example.com")
                    }
                }
                scm {
                    connection.set("scm:git:git@github.com:example/platform.git")
                    url.set("https://github.com/example/platform")
                }
            }
        }
    }
    repositories {
        maven {
            name = "internal"
            url = uri(providers.gradleProperty("internalRepoUrl").get())
            credentials {
                username = providers.environmentVariable("REPO_USER").get()
                password = providers.environmentVariable("REPO_PASSWORD").get()
            }
        }
    }
}
```

Publish to internal Nexus/Artifactory for proprietary code; Maven Central for open source.

### Artifact Signing

```kotlin
signing {
    val signingKey = providers.environmentVariable("SIGNING_KEY").orNull
    val signingPassword = providers.environmentVariable("SIGNING_PASSWORD").orNull
    if (signingKey != null && signingPassword != null) {
        useInMemoryPgpKeys(signingKey, signingPassword)
        sign(publishing.publications["maven"])
    }
}
```

Maven Central requires signed artifacts; internal repositories may not require signing but benefit from tamper detection.

### Application Distribution

Use the `application` plugin for executable JVM applications:

```kotlin
plugins {
    application
    alias(libs.plugins.shadow)
}

application {
    mainClass.set("com.company.servicex.Main")
    applicationDefaultJvmArgs = listOf("-Xmx512m")
}

tasks.named<com.github.jengelman.gradle.plugins.shadow.tasks.ShadowJar>("shadowJar") {
    archiveClassifier.set("all")
    mergeServiceFiles()
}
```

The `shadow` plugin produces a fat JAR with merged service files and relocated dependencies.

---
[Back to Overview](./OVERVIEW.md)
