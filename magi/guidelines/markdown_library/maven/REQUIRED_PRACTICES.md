# Required Practices

### Always Do

- Use semantic versioning for releases.
- Declare all plugin versions explicitly.
- Keep POM files clean and well-organized.
- Use `dependencyManagement` for version control.
- Configure encoding explicitly (`UTF-8` for `project.build.sourceEncoding` and `project.reporting.outputEncoding`).
- Include comprehensive test coverage.
- Use profiles for environment-specific configuration.
- Document any deviations from conventions.
- Keep build output deterministic and reproducible (`project.build.outputTimestamp`).
- Use the standard Maven directory layout.
- Configure essential plugins (compiler, surefire, failsafe).
- Use BOM imports for framework dependencies.
- Validate dependency convergence with `maven-enforcer-plugin`.
- Use CI-friendly versioning (`${revision}${changelist}${sha1}`) for automation.
- Run a §17 shakedown after every artifact-affecting change.

---
[Back to Overview](./OVERVIEW.md)
