# Webhook Architecture

WooCommerce webhooks push event notifications to external systems when resources change. **Webhooks are the primary mechanism for integrating WooCommerce with fulfillment services, ERPs, CRMs, analytics platforms, and custom microservices.**

### Signature Verification

**Verify webhook signatures on every incoming request.** WooCommerce signs webhook payloads with HMAC-SHA256 using the webhook's secret key, delivered in the `X-WC-Webhook-Signature` header. Compute HMAC-SHA256 of the **raw request body** using the stored webhook secret and compare against the header value. **Reject requests with missing or mismatched signatures. Unverified webhook payloads are untrusted internet input.**

### Idempotency

**Process webhook payloads idempotently.** WooCommerce retries failed deliveries (HTTP response outside 2xx) with increasing delays. Duplicate deliveries are expected. **Deduplicate using the `X-WC-Webhook-Delivery-ID` header** or the `webhook_id + resource_id` combination. Store processed delivery IDs and skip duplicates.

### Fast Acknowledgment

**Return HTTP 200 quickly.** WooCommerce expects a response within the configured timeout (default 5 seconds, configurable via `woocommerce_webhook_deliver_timeout`). **Long-running processing must be enqueued for background execution.** Return 200 to acknowledge receipt, then process asynchronously.

### Topic Selection and Versioning

- **Subscribe to the minimum set of topics needed.** Common topics: `order.created`, `order.updated`, `order.deleted`, `product.created`, `product.updated`, `product.deleted`, `customer.created`, `customer.updated`. Each active webhook adds overhead to every resource save operation — WooCommerce evaluates all webhook conditions on every relevant resource change.
- **Use the `wc/v3` webhook payload format.** Specify the API version during webhook creation. Payload structure varies between API versions — pinning the version ensures consistent payload shape regardless of the WooCommerce version running on the server.

### Health Monitoring

Monitor webhook delivery health in WooCommerce > Settings > Advanced > Webhooks. **WooCommerce disables webhooks after repeated delivery failures** (default: 5 consecutive failures). Implement alerting on webhook failure rates. When a webhook is auto-disabled, manually re-enable after fixing the delivery endpoint and investigate the missed events.

### Internal Hooks vs HTTP Webhooks

For high-volume event processing, consider using Action Scheduler hooks (`woocommerce_order_status_changed`, `woocommerce_new_order`) directly rather than HTTP webhooks. **Internal hooks avoid HTTP overhead, signature verification latency, and network failure modes.** Use HTTP webhooks only when the consumer is an external system that cannot run within the WordPress process.

---
[Back to Overview](./OVERVIEW.md)
