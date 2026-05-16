# Real User Monitoring (RUM) Integration

### Initialization

```javascript
import { datadogRum } from '@datadog/browser-rum';

datadogRum.init({
    applicationId: 'YOUR_APPLICATION_ID',
    clientToken: 'YOUR_CLIENT_TOKEN',
    site: 'datadoghq.com',
    service: 'frontend-app',
    env: 'production',
    version: '1.2.3',
    sessionSampleRate: 100,
    sessionReplaySampleRate: 20,
    trackUserInteractions: true,
    trackResources: true,
    trackLongTasks: true,
    defaultPrivacyLevel: 'mask-user-input'
});

// Set user context
datadogRum.setUser({
    id: '1234',
    name: 'John Doe',
    email: 'john@example.com',
    tier: 'enterprise'
});

// Add global context
datadogRum.setGlobalContextProperty('feature_flags', {
    new_checkout: true,
    beta_features: false
});
```

### Custom Actions and Errors

```javascript
// Track custom user actions
datadogRum.addAction('checkout_started', {
    cart_value: 150.00,
    item_count: 3,
    payment_method: 'credit_card'
});

// Track custom errors
try {
    processPayment();
} catch (error) {
    datadogRum.addError(error, {
        context: 'payment_processing',
        user_tier: 'premium'
    });
}

// Track custom timing
datadogRum.addTiming('api_call_duration', 1234);
```

### Privacy Configuration

| Setting | Purpose |
|:--------|:--------|
| `defaultPrivacyLevel` | `mask-user-input` (recommended), `allow`, or `mask` — controls sensitive data collection |
| `trackFrustrations` | Track rage clicks and dead clicks |
| `beforeSend` | Filter or modify RUM events before sending |

---
[Back to Overview](./OVERVIEW.md)
