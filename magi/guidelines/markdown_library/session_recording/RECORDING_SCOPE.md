# Recording Scope and Sampling

Recording every session for every user generates enormous data volumes, increases PII exposure surface, increases cost, and rarely delivers proportional analytical value. **Strategic scoping reduces all four without sacrificing insight quality.**

### Session Sampling

| Coverage | When |
|:--------:|:-----|
| 10–25% sample | Statistically representative behavioral data for UX analysis |
| 100% recording | Justified only for error-triggered replays or critical funnels (checkout, onboarding) |

Configure sampling in the SDK initialization:

| SDK | Sampling parameter |
|:----|:-------------------|
| OpenReplay | `captureRate` |
| FullStory | `sampling` |
| Sentry | `replaysSessionSampleRate` |

### Error-Triggered Recording

Capture **100% of sessions where JavaScript errors occur**, while sampling routine sessions at a lower rate:

```javascript
{
    replaysSessionSampleRate: 0.1,    // 10% of normal sessions
    replaysOnErrorSampleRate: 1.0,    // all error sessions
}
```

This maximizes debugging value while minimizing data volume for non-error sessions.

### Route Exclusion

Exclude pages and routes that have no analytical value or contain high-sensitivity content:

- `/admin`
- `/internal`
- `/account/security`

Configure route-based exclusion in the SDK or via conditional initialization. Recording these provides minimal UX insight and maximum PII exposure.

### Session Duration Cap

Sessions that exceed 60–90 minutes are likely idle tabs, not active usage. Cap recording duration to avoid storing hours of inactive browser tabs that consume storage without providing actionable data.

### Internal User Exclusion

Do not record sessions for authenticated internal users (employees, support staff, developers) unless debugging a specific reported issue. Identify internal users by:

- IP range
- Authenticated email domain
- Cookie flag

Internal sessions pollute behavioral analytics, contain access to admin interfaces, and may capture internal communications or sensitive operational data.

---
[Back to Overview](./OVERVIEW.md)
