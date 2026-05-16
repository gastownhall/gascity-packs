# API Versioning and Upgrades

### API Version Pinning

Pin the Stripe API version in SDK initialization:

```javascript
new Stripe(secretKey, { apiVersion: '2024-12-18' });
```

This ensures consistent API behavior **regardless of the Stripe account's default version**.

**Webhook events use the version configured on the webhook endpoint, not the SDK version.** When upgrading API versions, review the changelog for breaking changes, update the SDK, test all integration paths, and **update the webhook endpoint version simultaneously**.

### Upgrade Strategy

- **Upgrade API versions proactively.** Stripe maintains backward compatibility within a version but deprecates older versions over time.
- Test version upgrades in staging with test-mode keys against the full webhook event catalog.
- Pay attention to changes in object shapes, removed fields, renamed parameters.
- The Stripe SDK changelog and API upgrade guide document every breaking change.
- Schedule upgrades **quarterly** alongside key rotation.

---
[Back to Overview](./OVERVIEW.md)
