# Style Summary

| Element | Required Style |
|:--------|:---------------|
| Project Structure | Follow Maven standard directory layout |
| POM Organization | Consistent element ordering; properties first |
| Dependencies | Use `dependencyManagement`; explicit scopes; pinned versions |
| Plugins | All versions declared; essential plugins configured |
| Multi-Module | Parent POM manages versions; modules reference siblings without versions |
| Profiles | Environment-specific; clear activation rules; CI-friendly versioning |
| Properties | Centralized version management; descriptive names; `outputTimestamp` for reproducibility |
| Java | Java 21+; records, sealed classes, pattern matching, virtual threads |
| Spring Boot | `spring-boot-starter-parent`; `spring-boot-maven-plugin` with layers + image; native via `native-maven-plugin` |
| Testing | Surefire (unit) + Failsafe (IT); JaCoCo with 80% instruction / 70% branch thresholds |
| Release | `maven-release-plugin` with `tagNameFormat=v@{project.version}`; CI-friendly versioning override |
| CI/CD | GitHub Actions / Jenkins / GitLab; `mvn -B verify` on clean agent; coverage upload |
| Deployment | Repository configuration; release automation |
| Resources | Proper filtering; environment-specific handling |
| Naming | Lowercase with hyphens; semantic versioning |
| Documentation | Clear descriptions; documented deviations |
| Shakedown | `verify`-phase profile against packaged artifact + Testcontainers; classify pass / fail-blocking / fail-nonblocking / inconclusive |
| Defense in Depth | Enforcer + BOM + checksums/locks + reproducible builds + CI clean build + vulnerability scan + shakedown |
| Rule of Three | Local build + clean-CI build + dependency/license scan MUST agree before release |

---
[Back to Overview](./OVERVIEW.md)
