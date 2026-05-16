# Security

WooCommerce handles financial transactions and customer PII. **Security failures result in financial loss, regulatory penalties, and irreversible brand damage.**

### HTTPS Everywhere

**All WooCommerce admin and API traffic runs over HTTPS exclusively.** `FORCE_SSL_ADMIN` must be `true`. WooCommerce REST API consumer secrets transmitted over HTTP are compromised. Store API `Cart-Token` JWTs transmitted over HTTP are session-hijackable. **There is no legitimate use case for HTTP in a WooCommerce deployment.**

### Tokenized Payments Only

**Do not store raw credit card numbers, CVVs, or full card data** in WooCommerce or its database. WooCommerce's payment architecture uses tokenization — payment gateways return tokens or payment method IDs that WooCommerce stores as order meta. **Direct card handling requires PCI DSS SAQ D compliance**, which is beyond the scope of most WordPress installations. Use Stripe Elements, PayPal hosted fields, or equivalent embedded payment components that keep card data off your server.

### REST API IP Restriction

**Restrict WooCommerce REST API access by IP when possible.** Use application-level firewalls, Cloudflare Access, or NGINX allow/deny to limit which IPs can reach `/wp-json/wc/v3/`. The Store API (`/wp-json/wc/store/v1/`) must remain publicly accessible for customer-facing frontends but **should be protected by rate limiting**.

### Capability Audits

Regularly audit WooCommerce user capabilities. WooCommerce adds capabilities (`manage_woocommerce`, `edit_shop_orders`, `edit_products`, `view_woocommerce_reports`) that grant access to financial data and order management. **Verify that only authorized roles hold these capabilities.** Remove WooCommerce capabilities from roles that do not need them (e.g., editors should not have `manage_woocommerce` unless they are also shop managers).

---
[Back to Overview](./OVERVIEW.md)
