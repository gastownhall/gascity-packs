# Development Workflow

### Version Control

- Use Power BI Desktop **Developer Mode (PBIP format)** — each query serializes to an individual `.m` file.
- Track changes through standard Git workflow.
- External tool integration: **Tabular Editor** for model management; **ALM Toolkit** for deployment comparison; **pbi-tools** for PBIX unpacking.

### Branching Strategy

| Branch | Purpose |
|:-------|:--------|
| `main` | Production-ready queries; deployed to production workspace |
| `develop` | Integration branch for testing combined changes |
| `feature/xxx` | Individual feature development |
| `hotfix/xxx` | Emergency production fixes |

### Code Review Checklist

- Query folding preserved for source-connected steps.
- Types declared explicitly at ingestion.
- Parameters used for environment-specific values.
- Staging queries disabled from load.
- Error handling present for risky operations.
- Naming conventions followed consistently.
- No hardcoded credentials or paths.

### Deployment Pipeline

| Stage | Actions |
|:------|:--------|
| Development | Develop and test in Power BI Desktop; validate with query diagnostics; commit to feature branch |
| Staging | Merge to develop branch; deploy to staging workspace; run automated validation queries; verify refresh succeeds with production-like data |
| Production | Merge to main branch; deploy via Power BI deployment pipelines; configure incremental refresh (if applicable); monitor initial refresh |

### Documentation Standards

Document each query group:

- Purpose and business context.
- Source system dependencies.
- Refresh requirements and schedule.
- Known limitations or technical debt.

---
[Back to Overview](./OVERVIEW.md)
