# Shakedown — Verify-Phase Integration Validation

### Definition

A Maven shakedown is a **dedicated profile bound to the `verify` phase** that:

- Executes the **built artifact** against real infrastructure (Testcontainers-provisioned services or a staging endpoint).
- Runs failsafe integration tests against the **artifact as consumed** (not the pre-shade classpath).
- Confirms declared dependencies resolve at runtime.
- Verifies the final assembled JAR/WAR contains every required resource.

Shakedown is the first time the artifact is exercised as a **published unit** rather than a compilation output.

### Shakedown vs `test` vs `verify`

| Phase | Question Answered |
|:------|:------------------|
| `mvn test` | Do the units work? — runs unit tests against compiled classes; no shade/repackage/assembly |
| `mvn verify` (without shakedown) | Do the units compose? — runs failsafe ITs but does not exercise the artifact against real infra |
| **`mvn verify -P shakedown`** | **Does the artifact work in a real environment?** — provisions real services, runs the packaged artifact, validates the integrated whole |

### Mandatory Triggers

Shakedown is mandatory on:

- First release of a new artifact.
- Major or minor version bump of a framework dependency (Spring Boot, Jakarta EE, Quarkus).
- Changes to the shade or assembly plugin configuration affecting the final JAR contents.
- Addition or removal of a runtime-scoped dependency.
- Migration between packaging types.
- Java version upgrade.
- Repository coordinate change.
- CI/CD pipeline infrastructure change.

### Non-Triggers

- Patch-level dependency updates within a validated BOM.
- Javadoc-only changes.
- Unit test additions.
- Changes scoped entirely to `src/test/`.

### Validation Categories

1. **Runtime dependency resolution** — every transitively required class loads from the packaged artifact without `ClassNotFoundException` or `NoSuchMethodError`.
2. **Assembly completeness** — `META-INF/services` entries, `spring.factories`, resource bundles, and static resources are present in the final JAR/WAR.
3. **Executable entry point** — Spring Boot executable JARs start, respond to a health probe, and exit cleanly on a `--shakedown` flag if the application supports it.
4. **Infrastructure integration** — database connections, message queues, external service calls succeed against Testcontainers or staging endpoints.
5. **Configuration propagation** — externalized configuration is read from environment variables, `application.yml`, and command-line overrides in the correct precedence.
6. **Failsafe ITs against packaged classpath** — integration tests run against the packaged artifact classpath, not the compile classpath.

### Execution Principles

- **Conservative** — a representative integration scenario, not a full load test.
- **Progressive stress** — run packaged artifact with `--help` or no-op entry point → start against Testcontainers → execute failsafe suite → exercise shade/assembly validation.
- **Controlled environment** — Testcontainers images pinned by digest; staging endpoints with known fixture data; dedicated Maven repository for the shakedown build to avoid polluting the local cache.
- **Observable execution** — `-X` Maven debug on the shakedown profile execution, failsafe reports preserved, startup logs captured.
- **Known-good inputs** — fixture data seeded by Testcontainers init scripts.
- **No optimization** — record slow startup as a non-blocking observation and move on.

### Execution Pattern

| Step | Action |
|:----:|:-------|
| 1 | Confirm preflight: `mvn validate` passes; dependencies resolve offline; plugin versions pinned |
| 2 | Run `mvn verify -P shakedown` in an isolated build |
| 3 | Shakedown profile provisions Testcontainers or a staging target via a `BeforeSuite` hook |
| 4 | Artifact under validation is the packaged JAR/WAR from `${project.build.directory}` — **not** the exploded classes directory |
| 5 | Failsafe ITs execute against the real artifact classpath |
| 6 | Dedicated `exec-maven-plugin` execution launches the packaged Spring Boot JAR with `--shakedown`, asserts a clean exit |
| 7 | Assembly validation asserts required resources exist in the JAR via shade or assembly verification goal |
| 8 | All outputs record to `target/shakedown-reports/` |
| 9 | Classify result |

### Result Classification

- **Pass** — shakedown profile completes with zero failsafe failures; packaged artifact starts and exits cleanly; all assembly resources validated.
- **Fail-blocking** — any `ClassNotFoundException` at runtime; any failsafe IT failure; any missing `META-INF/services` or `spring.factories` entry; any executable JAR failing to start.
- **Fail-nonblocking** — slow startup exceeding an advisory threshold; warning-level log output; assembly artifacts larger than the prior baseline by an unexpected margin.
- **Inconclusive** — Testcontainers failed to provision; staging endpoint unreachable. Repair infrastructure and re-run the specific validation.

### Required Artifacts

- `target/shakedown-reports/` directory containing the Maven `-X` execution log, `failsafe-reports/` from the shakedown profile run, startup stdout/stderr capture for the exec-launched artifact, assembly validation report listing all verified resources.
- Environment snapshot: Maven version, JDK version, packaged artifact SHA-256, Testcontainers image digests, active Maven profiles, effective POM.

### Anti-Patterns (Forbidden)

- Running `mvn verify` without the shakedown profile and declaring the artifact validated.
- Using mocked dependencies in the shakedown failsafe suite.
- Running shakedown against the exploded `target/classes/` directory instead of the packaged JAR.
- Skipping assembly validation because "shade always worked before".
- Deleting `target/shakedown-reports/` on the next build without archiving.
- Downgrading a dependency version to fix a shakedown failure instead of addressing the root cause.

### Reference Shakedown Profile

```xml
<profiles>
    <profile>
        <id>shakedown</id>
        <properties>
            <skip.integration.tests>false</skip.integration.tests>
            <shakedown.reports.dir>${project.build.directory}/shakedown-reports</shakedown.reports.dir>
            <shakedown.artifact>${project.build.directory}/${project.build.finalName}.jar</shakedown.artifact>
        </properties>
        <dependencies>
            <dependency>
                <groupId>org.testcontainers</groupId>
                <artifactId>testcontainers</artifactId>
                <scope>test</scope>
            </dependency>
            <dependency>
                <groupId>org.testcontainers</groupId>
                <artifactId>postgresql</artifactId>
                <scope>test</scope>
            </dependency>
            <dependency>
                <groupId>org.testcontainers</groupId>
                <artifactId>junit-jupiter</artifactId>
                <scope>test</scope>
            </dependency>
        </dependencies>
        <build>
            <plugins>
                <!-- Failsafe runs the shakedown integration suite against the packaged artifact classpath -->
                <plugin>
                    <groupId>org.apache.maven.plugins</groupId>
                    <artifactId>maven-failsafe-plugin</artifactId>
                    <version>3.2.3</version>
                    <executions>
                        <execution>
                            <id>shakedown-it</id>
                            <phase>verify</phase>
                            <goals>
                                <goal>integration-test</goal>
                                <goal>verify</goal>
                            </goals>
                            <configuration>
                                <includes>
                                    <include>**/*ShakedownIT.java</include>
                                </includes>
                                <systemPropertyVariables>
                                    <shakedown.artifact>${shakedown.artifact}</shakedown.artifact>
                                    <shakedown.reports.dir>${shakedown.reports.dir}</shakedown.reports.dir>
                                </systemPropertyVariables>
                                <reportsDirectory>${shakedown.reports.dir}/failsafe</reportsDirectory>
                            </configuration>
                        </execution>
                    </executions>
                </plugin>
                <!-- Launch the packaged Spring Boot executable JAR with the application's shakedown flag and assert a clean exit -->
                <plugin>
                    <groupId>org.codehaus.mojo</groupId>
                    <artifactId>exec-maven-plugin</artifactId>
                    <version>3.1.1</version>
                    <executions>
                        <execution>
                            <id>shakedown-artifact-launch</id>
                            <phase>verify</phase>
                            <goals>
                                <goal>exec</goal>
                            </goals>
                            <configuration>
                                <executable>java</executable>
                                <arguments>
                                    <argument>-jar</argument>
                                    <argument>${shakedown.artifact}</argument>
                                    <argument>--shakedown</argument>
                                    <argument>--spring.profiles.active=shakedown</argument>
                                </arguments>
                                <successCodes>
                                    <successCode>0</successCode>
                                </successCodes>
                            </configuration>
                        </execution>
                    </executions>
                </plugin>
                <!-- Verify assembly completeness: required META-INF/services, spring.factories, and resource bundles exist in the packaged artifact -->
                <plugin>
                    <groupId>org.apache.maven.plugins</groupId>
                    <artifactId>maven-enforcer-plugin</artifactId>
                    <version>3.4.1</version>
                    <executions>
                        <execution>
                            <id>shakedown-assembly-validation</id>
                            <phase>verify</phase>
                            <goals>
                                <goal>enforce</goal>
                            </goals>
                            <configuration>
                                <rules>
                                    <requireFilesExist>
                                        <files>
                                            <file>${shakedown.artifact}</file>
                                        </files>
                                    </requireFilesExist>
                                </rules>
                            </configuration>
                        </execution>
                    </executions>
                </plugin>
            </plugins>
        </build>
    </profile>
</profiles>
```

---
[Back to Overview](./OVERVIEW.md)
