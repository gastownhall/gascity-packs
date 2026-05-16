# Webhooks

Webhooks deliver server-to-client events as outbound HTTPS POSTs to consumer-supplied endpoints.

### Webhook Payload Schema

```json
{
  "id": "evt_123",
  "type": "order.created",
  "apiVersion": "v1",
  "created": "2024-01-15T10:30:00Z",
  "data": { },
  "signature": "sha256=..."
}
```

### Webhook Security

Required:
- **HMAC signature verification** — every payload signed with a per-subscription secret
- **HTTPS endpoints only** — reject non-TLS receivers at registration time
- **Timestamp validation** — reject events older than a freshness window (typically 5 minutes) to prevent replay

Headers:
```
X-Webhook-Signature: sha256=<HMAC-SHA256(secret, raw_body)>
X-Webhook-Timestamp: 2024-01-15T10:30:00Z
```

Receivers MUST validate signature against the raw request body before parsing JSON.

### Webhook Reliability

| Aspect | Policy |
|:-------|:-------|
| Retry strategy | Exponential backoff |
| Max attempts | 5 |
| Timeout per attempt | 30 seconds |
| Success criterion | 2xx response status |
| Failure criterion | Non-2xx triggers retry |

### Webhook Registration Endpoints

```
POST   /webhooks    Register webhook
GET    /webhooks    List webhooks
PUT    /webhooks    Update webhook
DELETE /webhooks    Unregister webhook
```

```json
POST /webhooks
{
  "url": "https://example.com/webhook",
  "events": ["order.created", "order.updated"],
  "secret": "whsec_abc123"
}
```

---
[Back to Overview](./OVERVIEW.md)
