# Feature Flags and Dynamic Configuration

### Feature Flag Architecture

App Configuration provides native feature flag support with:
- Boolean on/off flags
- Percentage-based rollouts
- User/group targeting
- Time window activation
- Custom filter expressions

### Flag Naming

```
FeatureManagement:{FlagName}
```

Examples:
- `FeatureManagement:NewCheckoutFlow`
- `FeatureManagement:BetaReporting`
- `FeatureManagement:MaintenanceMode`

Wrong: `Flags:NewCheckout` (the prefix is `FeatureManagement:`).

### Targeting Filters

**Percentage Filter** — random rollout to X% of users:
```json
{
  "enabled": true,
  "conditions": {
    "client_filters": [
      { "name": "Microsoft.Percentage", "parameters": { "Value": 25 } }
    ]
  }
}
```

**Targeting Filter** — specific users/groups first:
```json
{
  "enabled": true,
  "conditions": {
    "client_filters": [
      {
        "name": "Microsoft.Targeting",
        "parameters": {
          "Audience": {
            "Users": ["user1@contoso.com"],
            "Groups": [{ "Name": "BetaTesters", "RolloutPercentage": 100 }],
            "DefaultRolloutPercentage": 0
          }
        }
      }
    ]
  }
}
```

### Dynamic Refresh

Applications poll App Configuration for changes rather than requiring restart:
- Configure refresh interval (minimum 1 second; **recommended 5+ minutes for production**)
- Designate **sentinel keys** that trigger full refresh when changed
- Handle refresh failures gracefully; continue with cached configuration

Sentinel keys enable atomic configuration updates: change multiple values, then update the sentinel to trigger refresh of all changes simultaneously.

### Flag Lifecycle

| Stage | Description |
|:------|:------------|
| Development | Flag created, default off, developer testing |
| Testing | Enabled in test environments |
| Rollout | Gradual percentage increase in production |
| GeneralAvailability | Fully enabled, targeting removed |
| Cleanup | Flag removed from code and configuration |

**Flags remaining in code after GA represent technical debt.** Establish maximum flag lifetime policies (90 days post-GA recommended) and enforce removal.

---
[Back to Overview](./OVERVIEW.md)
