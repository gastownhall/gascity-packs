# Infrastructure as Code in CI/CD

### Plan/Preview on Every PR

Run IaC plan/preview on every PR:
- `terraform plan`
- `pulumi preview`
- `bicep what-if`

Display the plan output in the PR comment or CI artifact for reviewer inspection.

### Pipeline-Only Apply

**Apply IaC changes only from the CI/CD pipeline, never from developer workstations.** Local applies create state drift, bypass code review, and bypass approval gates. **The pipeline is the single path for infrastructure changes to reach any environment.**

### Remote State

Store IaC state (Terraform state, Pulumi state) in a remote backend with locking, encryption, and access control. State files contain sensitive information. **Local state files committed to version control are a security incident.**

### Drift Detection

Run drift detection on a schedule (daily or weekly). Compare the declared IaC state against the actual infrastructure state. Alert on drift. **Drift indicates manual changes that bypass the pipeline** — they must be either imported into IaC or reverted.

---
[Back to Overview](./OVERVIEW.md)
