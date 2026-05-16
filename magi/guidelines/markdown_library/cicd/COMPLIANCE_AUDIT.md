# Compliance and Audit

### Log Retention

Retain pipeline run logs, approval records, and artifact metadata for the duration required by the applicable compliance framework (typically 1-7 years). Configure log retention in the CI platform and export to long-term storage (S3, GCS, Azure Blob) if the platform's default retention is insufficient.

### Separation of Duties

The person who authors a change must not be the sole approver of that change's deployment. Require at least one reviewer who is not the PR author. For production deployments, require approval from a distinct set of approvers with deployment authority.

### Deployment Audit Reports

Generate reports tracing every production deployment to:
- Deployer identity
- Approval record
- Artifact digest
- Source commit SHA
- Pipeline run that built the artifact
- Test results for that run

This end-to-end traceability is the backbone of compliance evidence.

### Pipeline Definition Protection

Changes to CI workflow files (`.github/workflows`, `.gitlab-ci.yml`, `Jenkinsfile`, `azure-pipelines.yml`) require the same review rigor as application code. Use CODEOWNERS or equivalent to require specific reviewers for pipeline configuration changes. **A modified pipeline definition is a modified security control.**

---
[Back to Overview](./OVERVIEW.md)
