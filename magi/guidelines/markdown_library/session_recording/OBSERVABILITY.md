# Observability Integration

Session recordings gain maximum debugging value when correlated with backend logs, error tracking, APM traces, and analytics events. Integration connects **what the user experienced** (replay) with **what the system did** (logs, traces, errors).

### Session ID Propagation

Propagate a session ID from the recording SDK to backend requests:

| SDK | Mechanism |
|:----|:----------|
| OpenReplay | Session ID added as request header (`X-OpenReplay-SessionId`) to correlate backend logs with the frontend session |
| Sentry | Native integration — errors link directly to the replay at the moment the error occurred |

Configure correlation for every integration between the recording platform and backend observability tools.

### Error Tracking Integration

Integrate session replay with error tracking (Sentry, Datadog, Rollbar, Bugsnag). When a JavaScript error occurs, the replay provides the **exact user actions leading to the error** — eliminating "steps to reproduce" from bug reports. Verify the integration by triggering a test error and confirming the error report links to the correct replay moment.

### Backend Log Correlation

For OpenReplay self-hosted, integrate with the organization's logging platform (Elasticsearch, Datadog, CloudWatch, Stackdriver) to correlate backend events with session replays. Use the session ID as the correlation key. This enables support engineers to jump from a customer's support ticket → recording of their session → backend logs for that session, in a single workflow.

---
[Back to Overview](./OVERVIEW.md)
