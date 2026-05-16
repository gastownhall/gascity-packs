# Monitoring, Observability, and Feedback

### Pipeline Metrics

Track and display:
- Average duration
- Success rate
- Failure rate by stage
- Queue wait time
- Runner utilization

Publish to a dashboard visible to the team. **Pipeline performance degrades gradually without monitoring** — what was a 5-minute pipeline becomes 25 minutes over six months without anyone noticing.

### Main Branch Failure Alerts

Alert on pipeline failures for the main branch. Feature branch failures are the developer's responsibility. **Main branch failures block the entire team and require immediate attention.**

### DORA Metrics

Track the four DORA metrics:

| Metric | Question |
|:-------|:---------|
| Deployment frequency | How often does code reach production? |
| Lead time for changes | Commit to production duration |
| Change failure rate | % of deployments causing incidents |
| Mean time to recovery | Time to restore service after an incident |

Measure them, display them, and improve them systematically.

### Post-Deployment Monitoring

After deployment, monitor key metrics (error rate, latency, business KPIs) for 5-15 minutes. If metrics degrade beyond thresholds during the observation window, trigger automatic rollback or alert the deployer.

---
[Back to Overview](./OVERVIEW.md)
