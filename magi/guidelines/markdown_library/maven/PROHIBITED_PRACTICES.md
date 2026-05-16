# Prohibited Practices

### Never Do

- Use SNAPSHOT dependencies in production releases.
- Hardcode version numbers in child POMs.
- Include credentials in POM files.
- Use `LATEST` or `RELEASE` version specifiers.
- Mix packaging types in the same directory.
- Ignore dependency convergence warnings.
- Use `system` scope dependencies.
- Commit `target/` directories to version control.
- Override Maven conventions without documentation.
- Use deprecated plugins or configurations.
- Skip essential build phases without reason.
- Include environment-specific configuration in JAR files.
- Use relative paths outside the project structure.
- Downgrade package versions to suppress compatibility issues.
- Run `mvn verify` without the shakedown profile and declare the artifact validated.

---
[Back to Overview](./OVERVIEW.md)
