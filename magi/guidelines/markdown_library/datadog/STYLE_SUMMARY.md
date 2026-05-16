# Style Summary

| Category | Key Principles |
|:---------|:---------------|
| **Tagging** | Consistent naming, required tags on all telemetry, cardinality management |
| **Metrics** | `namespace.entity.attribute` naming, appropriate types, SLI/SLO alignment |
| **Logs** | Structured JSON, log levels, sampling, retention tiers |
| **Traces** | Context propagation, intelligent sampling, span naming |
| **Alerting** | Actionable, severity-based, runbook-documented, SLO-driven |
| **Dashboards** | Golden signals, RED/USE methods, hierarchical structure |
| **Synthetics** | API + browser + multi-step from multiple regions |
| **RUM** | Client-side errors, Core Web Vitals, privacy-aware (`mask-user-input` default) |
| **Multi-tenancy** | Tenant tagging, noisy neighbor detection, per-tenant dashboards |
| **Baselines** | Time-based, load-based, anomaly detection |
| **Cost** | Log exclusion/sampling, metric cardinality, trace sampling |
| **Security** | Data scrubbing, RBAC, audit logging, compliance alignment |
| **Shakedown** | Real Agent emission + Datadog API verification + classified outcome |
| **Defense in Depth** | Metrics + logs + traces + synthetics + RUM + alerts/SLOs + dashboards/runbooks + shakedown |

Following this guide produces observability that enables rapid incident response, provides actionable insights, maintains cost efficiency, and meets compliance requirements. Every metric, log, and trace carries context that answers the fundamental questions: What happened? When? Where? To whom? Why? The shakedown layer ensures the telemetry pipeline itself works — because observability of broken observability is the worst incident.

---
[Back to Overview](./OVERVIEW.md)
