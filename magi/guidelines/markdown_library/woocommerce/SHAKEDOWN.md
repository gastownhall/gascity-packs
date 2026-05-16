# Shakedown — End-to-End Commerce Validation

A WooCommerce shakedown is a **mandatory, end-to-end integration-validation pass that drives a real transaction through the commerce pipeline against a real (sandbox) payment gateway**. It answers one question: **does the store actually transact when the cart, checkout, payment gateway, tax engine, shipping engine, inventory system, email dispatcher, webhook subscribers, and order-status hooks all fire together?** The WordPress platform shakedown confirms the CMS runs. **The WooCommerce shakedown confirms the store sells.**

### Mandatory Real-Pipeline Execution

**Every WooCommerce shakedown drives a real transaction through the full pipeline:**

```text
add-to-cart → coupon apply → shipping selection → tax calculation →
checkout submission → sandbox gateway authorization → order creation →
inventory decrement → order-confirmation email → webhook fan-out
```

**Synthetic paths that stop short of sandbox gateway authorization or that mock the gateway response are not shakedowns — they are unit tests.**

### Definition

A WooCommerce shakedown is the first controlled, end-to-end execution of the commerce pipeline under real but bounded conditions:

- Real `WC_Cart` session.
- Real Store API or shortcode checkout.
- **Real sandbox Stripe or PayPal test credentials (not mocks)**.
- Real `wc_get_orders()` order persistence.
- Real `wc_mail` dispatch into a mail catcher or test inbox.
- Real webhook delivery to a subscriber endpoint.
- Real `WC_Session` persistence across requests.
- Real tax calculation against the canary address.
- Real inventory decrement on order placement.

The shakedown executes a small number of representative transactions with known inputs and known expected outputs.

### Preflight vs Shakedown vs Testing

| Phase | What it validates |
|:------|:------------------|
| **Preflight** | `wp wc hpos status` confirms HPOS enabled. `wp wc status` reports clean. Required plugins active. Tax tables, shipping zones exist. **Answers: "can the store attempt to transact"** |
| **Shakedown** | Drives a real sandbox transaction through the full pipeline. Confirms every subsystem (cart, session, coupon, shipping, tax, gateway, order store, inventory, email, webhook bus) responds correctly together. **Answers: "does the store transact"** |
| **Testing** | Load testing, regression testing, acceptance testing across many variations. **Answers: "is the store reliable, correct, and fast enough"** |

A store that passes preflight is **bootable**. A store that passes shakedown is **transactional**. A store that passes testing is **reliable**.

### Mandatory Triggers

A WooCommerce shakedown is mandatory after:

- WooCommerce core update (minor or major), including point releases that touch the checkout block or the cart block.
- Payment gateway plugin update, addition, removal, or API-key rotation (Stripe, PayPal, Authorize.net, Square, Klarna, Affirm).
- Payment gateway settings change: mode switch (test ↔ live), webhook endpoint URL change, supported payment methods change.
- Shipping method addition, removal, zone reconfiguration, or rate change on carrier-integrated plugins.
- Tax configuration change: rate import, automated tax service enable/disable, prices-entered-with-tax toggle, tax class reassignment.
- Checkout template override added or modified, or checkout block configuration change.
- WooCommerce extension update: Subscriptions, Memberships, Bookings, Product Bundles, Composite Products.
- HPOS migration: compatibility mode enable, sync run, authoritative storage switch, or legacy data cleanup.
- Webhook subscriber change: endpoint URL change, secret rotation, topic subscription change.
- Custom product type registration or `product_type_selector` filter modification.
- Session storage change (`WC_Session_Handler` override, Cart-Token middleware update, headless frontend domain change).
- GDPR/CCPA compliance hook change affecting checkout consent, account deletion, or data export flows.

### Non-Triggers

- Product content edits (title, description, image, category) that do not change price, tax class, or stock status.
- Coupon creation within the existing coupon engine configuration.
- Order admin actions performed manually (status transitions via admin, refund processing through gateway admin).
- Customer account edits, address changes, role adjustments that do not touch WooCommerce capabilities.
- Email template copy edits within the child theme's `woocommerce/emails/` override directory (unless the template structure itself changes).

### Validation Categories

| Category | What is verified |
|:---------|:-----------------|
| **Data flow integrity** | Product page renders correct price/tax/stock. Add-to-cart returns updated cart with correct line item, qty, subtotal, tax, shipping. Checkout produces order with correct totals — and **the amount captured by the gateway matches the order total to the cent**. Order, admin screen, and confirmation email all expose identical data |
| **Subsystem communication** | `WC_Cart` reads/writes `WC_Session` consistently across requests. Gateway SDK authenticates to sandbox API and gets a valid token/charge. Tax engine returns the expected rate for the canary address. Shipping engine returns expected method set. Webhook dispatcher delivers `order.created` with valid `X-WC-Webhook-Signature`. Email subsystem hands off to the configured provider and confirmation lands in the mail catcher |
| **Resource availability** | `WC_Session` rows created in `wp_woocommerce_sessions` (or object cache) on cart init and released on expiration. **Inventory decrements exactly once on order placement — not zero, not two.** Order persisted to `wp_wc_orders` exactly once with exactly one set of line items. No orphans, no duplicates |
| **Configuration propagation** | WooCommerce settings (base location, currency, tax rounding, prices-entered-with-tax, calculate-tax-based-on) propagate to cart and checkout calculations. Gateway sandbox keys reach the SDK. Shipping zones load and match the canary. Webhook secrets sign deliveries. `FeaturesUtil::declare_compatibility()` from every active extension propagates and HPOS is not downgraded |
| **Error handling paths** | A declined sandbox card (Stripe `4000 0000 0000 0002`) produces a clean error, the order sits at `pending` or fails cleanly, **inventory is not decremented**, no duplicate email/webhook. A webhook subscriber returning 500 triggers retry without double-dispatch. A tax service timeout falls back to local rates, not zero-tax |
| **Side effect correctness** | Order-confirmation email arrives **exactly once** with correct content. Webhook delivery fires **exactly once** per subscribed topic per order. Inventory decrement happens **exactly once**. Status transition hooks each fire **exactly once**. GDPR/CCPA hooks fire iff customer opted in. Subscription lifecycle hooks fire iff order contains a subscription |

### Execution Principles

- **Conservative** — Single shakedown product (known SKU, known price, known tax class, known stock), single coupon (known code, known discount), single canary shipping address (known zone, known rate), single test customer, single sandbox payment method with known success response.
- **Progressive stress** — Run the simplest guest checkout first (one product, no coupon, flat-rate shipping, no tax). Then layer complexity: add the coupon, switch to a taxed address, switch to a subscription product, switch to an authenticated customer with persistent cart. **Stop at the first failure.**
- **Controlled environment** — Staging WooCommerce against sandbox Stripe, sandbox PayPal, sandbox tax service credentials, and a mail catcher (MailHog, Mailtrap). Webhook subscribers point to a request-capture endpoint (RequestBin, webhook.site, or a staging consumer) that **records deliveries without executing production fulfillment**.
- **Observable execution** — `WC_LOG_HANDLER` logging to file, `WP_DEBUG` and `WP_DEBUG_LOG` enabled, gateway SDK debug mode, mail catcher tail, webhook capture tail. **Every log line is captured** for the artifact set.
- **Known-good inputs** — Versioned fixture set: shakedown product SKU, coupon code, canary address, customer, sandbox card, expected order total, expected tax, expected shipping. **Every shakedown run diffs actual against expected.**
- **No optimization** — Log slow checkout, slow tax lookups, slow webhook deliveries, but **do not tune during the pass**. Performance tuning is a testing concern.

### Execution Pattern

1. **Confirm preflight**: `wp wc hpos status` reports enabled and authoritative, `wp wc status` reports clean, all required plugins active, payment gateway in test mode, shipping zones exist, tax loaded, `WC_Session` table reachable.
2. **Initialize controlled environment**: clear `WC_Session` rows older than shakedown start, clear webhook capture endpoint, clear mail catcher inbox, truncate WooCommerce log files for this session, set gateway mode to test explicitly.
3. **Execute simplest happy path**: guest user, one unit of shakedown product, canary address with known shipping rate, no coupon, successful sandbox card. Verify cart totals before checkout submit.
4. **Submit checkout and verify the order**: capture new order ID, `wc_get_order()->get_total()` matches expected, `get_line_items()` returns exactly one item with expected SKU/qty, `get_shipping_total()` matches, `get_total_tax()` matches, `get_payment_method()` matches, `get_status()` is `processing`.
5. **Verify inventory**: shakedown product stock decremented by exactly one. No other product changed.
6. **Verify the order-confirmation email**: mail catcher received exactly one message addressed to the test customer; subject matches expected template; body contains order number, line items, totals.
7. **Verify webhook fan-out**: webhook capture endpoint received `order.created` and `order.updated` deliveries with valid `X-WC-Webhook-Signature`; deliveries match subscribed topic count — no extras, no missing.
8. **Verify session persistence**: follow-up request with same `Cart-Token` returns now-empty cart without errors. Cart abandonment scenario releases inventory correctly.
9. **Execute coupon path**: repeat happy path with shakedown coupon applied. Verify discount reaches order line items and total. Verify coupon usage count increments by exactly one.
10. **Execute failure path**: attempt checkout with sandbox declined card (Stripe `4000 0000 0000 0002`). Verify clean error, no paid-state order, no inventory decrement, no confirmation email, no `order.created` webhook for a successful order.
11. **Execute tax canary**: change checkout address to a known-taxable jurisdiction; re-run happy path; verify tax total matches expected rate table value.
12. **Execute subscription lifecycle** (if Subscriptions active): purchase shakedown subscription product, advance next-payment date via CLI, trigger renewal, verify renewal charge succeeds, verify subscription status transitions correctly.
13. **Record observations, classify the pass, produce artifact set.**

### Reference Shakedown Harness

```php
<?php
declare( strict_types=1 );

/**
 * WooCommerce shakedown harness.
 *
 * Preconditions:
 *   - Stripe gateway in test mode with sandbox keys loaded.
 *   - Shakedown product SKU 'SHAKEDOWN-CANARY' exists with price 42.00 and stock 100.
 *   - Coupon 'SHAKEDOWN15' exists with 15% off.
 *   - Shipping zone for canary address has flat rate 9.99.
 *   - Tax rate for canary jurisdiction is 8.25%.
 *   - MailHog running on localhost:1025, captured via WP Mail SMTP.
 *   - Webhook endpoint points to webhook.site capture URL.
 */

require_once __DIR__ . '/wp-load.php';

if ( ! defined( 'WP_CLI' ) || ! WP_CLI ) {
    fwrite( STDERR, "Must run via WP-CLI: wp eval-file wc-shakedown.php\n" );
    exit( 1 );
}

$expected = [
    'line_subtotal' => 42.00,
    'shipping'      => 9.99,
    'tax'           => 4.29, // (42.00 - (42.00 * 0.15)) * 0.0825 rounded
    'discount'      => 6.30, // 42.00 * 0.15
    'total'         => 49.98, // subtotal(42) - discount(6.30) + shipping(9.99) + tax(4.29) rounded
    'sku'           => 'SHAKEDOWN-CANARY',
    'coupon'        => 'shakedown15',
];

$product = wc_get_product( wc_get_product_id_by_sku( $expected['sku'] ) );
if ( ! $product instanceof WC_Product ) {
    WP_CLI::error( 'Shakedown product missing' );
}

$stock_before = $product->get_stock_quantity();

WC()->cart->empty_cart();
WC()->cart->add_to_cart( $product->get_id(), 1 );
WC()->cart->apply_coupon( $expected['coupon'] );
WC()->customer->set_shipping_country( 'US' );
WC()->customer->set_shipping_state( 'WA' );
WC()->customer->set_shipping_postcode( '98101' );
WC()->cart->calculate_totals();

$order = wc_create_order();
foreach ( WC()->cart->get_cart() as $cart_item ) {
    $order->add_product( $cart_item['data'], $cart_item['quantity'] );
}
$order->set_address( [
    'first_name' => 'Shakedown',
    'last_name'  => 'Canary',
    'email'      => 'shakedown@example.test',
    'country'    => 'US',
    'state'      => 'WA',
    'postcode'   => '98101',
], 'billing' );
$order->set_payment_method( 'stripe' );
$order->calculate_totals();

$gateway  = WC()->payment_gateways->payment_gateways()['stripe'];
$response = $gateway->process_payment( $order->get_id() );
if ( ! isset( $response['result'] ) || 'success' !== $response['result'] ) {
    WP_CLI::error( 'Sandbox gateway rejected canary transaction' );
}

$order = wc_get_order( $order->get_id() );

$checks = [
    'total'    => abs( (float) $order->get_total() - $expected['total'] ) < 0.01,
    'shipping' => abs( (float) $order->get_shipping_total() - $expected['shipping'] ) < 0.01,
    'tax'      => abs( (float) $order->get_total_tax() - $expected['tax'] ) < 0.01,
    'discount' => abs( (float) $order->get_discount_total() - $expected['discount'] ) < 0.01,
    'status'   => in_array( $order->get_status(), [ 'processing', 'completed' ], true ),
];

$product_after = wc_get_product( $product->get_id() );
$stock_after   = $product_after->get_stock_quantity();
$checks['inventory_decrement'] = ( $stock_before - $stock_after ) === 1;

foreach ( $checks as $name => $passed ) {
    if ( ! $passed ) {
        WP_CLI::error( "Shakedown FAIL-BLOCKING: {$name}" );
    }
}

WP_CLI::success( sprintf( 'Shakedown PASS order_id=%d total=%.2f', $order->get_id(), $order->get_total() ) );
```

### Result Classification

| Outcome | Trigger |
|:--------|:--------|
| **Pass** | Every commerce flow completed as expected. Totals matched, inventory decremented correctly, email delivered, webhooks fired, subscription lifecycle ticked through, failure paths failed cleanly. **Cleared for promotion** |
| **Fail-blocking** | Checkout errored, order total mismatch, gateway auth failed, inventory did not decrement, email did not send, webhook did not fire, subscription renewal threw. **Fix root cause and re-run from step 1** |
| **Fail-nonblocking** | Deprecation notice in gateway plugin, slow tax service response, webhook delivery slower than target latency. Log and proceed with caution |
| **Inconclusive** | Sandbox gateway rate-limited, mail catcher unreachable, tax service sandbox returned 503. Adjust and re-run the specific validation |

### Required Artifacts

- **Execution log** — Timestamped log of every command run, every HTTP request/response, contents of `wp-content/uploads/wc-logs/` for the shakedown window, `WP_DEBUG` log excerpts, WordPress and web server error logs.
- **Result summary** — Pass/fail classification per validation category (data flow, subsystem communication, resource availability, configuration propagation, error handling, side effects) with the specific flow and step that produced the classification.
- **Order fixtures** — Created order IDs, order JSON exports (`wp wc order get {id} --format=json`), captured webhook payloads, captured email bodies, actual-vs-expected diff per flow.
- **Environment snapshot** — WooCommerce version, HPOS status, active extension list with versions, active payment gateway plugins with versions and mode (test/live), active shipping methods, tax configuration summary, webhook subscriber list with secrets redacted, child theme version.

### Anti-Patterns

- **Mocking the payment gateway.** A shakedown that never contacts the real sandbox API does not validate gateway integration — it validates the mock. **Use real sandbox credentials.**
- **Skipping the failure path.** Happy-path-only ignores the error-handling validation category. **The decline card is mandatory.**
- **Running against a stripped staging environment** that omits production webhook subscribers, production tax service, or production email provider. Each omission defeats a validation category.
- **Treating shakedown as a regression suite.** Shakedown exercises a small number of canonical transactions. Regression testing exercises hundreds of variations. **Different purposes.**
- **Skipping shakedown after a "small" payment gateway plugin update.** Gateway updates touch the checkout block, Store API payment method registration, webhook handler, and `process_payment` method — every one is an integration boundary.
- **Failing to diff totals.** Producing an order and declaring success without verifying total/tax/shipping/line items match the expected fixture is **not a shakedown — it is a hope**.
- **No artifact capture.** Without order JSON, webhook payloads, and email bodies, **there is no proof the shakedown ran**.

---
[Back to Overview](./OVERVIEW.md)
