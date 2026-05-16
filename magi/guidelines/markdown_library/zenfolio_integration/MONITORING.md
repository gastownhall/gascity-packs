# Monitoring and Observability

### Proxy-Level Metrics

Track:

- API call count per method per minute.
- Average response time per method.
- Cache hit ratio.
- Error rate by error type.
- Token refresh frequency.

Publish to the organization's monitoring platform (Datadog, Prometheus, CloudWatch).

### Alerting Thresholds

| Condition | Alert |
|:----------|:------|
| Cache hit ratio < 80% | Cache misconfiguration |
| Error rate > 5% | API issue or integration bug |
| Token refresh failure | Credential issue |

### Frontend Metrics

Track via Real User Monitoring (RUM):

- Gallery load time (navigation to rendered grid).
- Photo grid time-to-interactive.
- Lightbox open latency.
- Search response time.
- **Core Web Vitals (LCP, INP, CLS)** must not regress when galleries load.

If LCP exceeds 2.5 seconds for gallery pages, investigate proxy latency, image size selection, or SSR configuration.

### Status Monitoring

Monitor Zenfolio's service status (`status.zenfolio.com`) and subscribe to status notifications. **Correlate integration errors with Zenfolio service incidents.** During known Zenfolio outages, serve extended-TTL cached data and display a non-alarming "Gallery content may be temporarily unavailable" notice rather than full error pages.

---
[Back to Overview](./OVERVIEW.md)
