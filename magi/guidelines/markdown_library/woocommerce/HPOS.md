# High-Performance Order Storage (HPOS)

HPOS moves order data from the WordPress EAV schema (`wp_posts` + `wp_postmeta`) to normalized, indexed custom tables (`wp_wc_orders`, `wp_wc_order_addresses`, `wp_wc_order_operational_data`, `wp_wc_orders_meta`). This delivers up to **5× faster order creation** and **40× faster admin filtering** for large catalogs. **HPOS is the mandatory storage backend for all new installations** and the migration target for all existing stores.

### CRUD-Only Order Access

| Operation | Required API | Forbidden |
|:----------|:-------------|:----------|
| Read order field | `$order->get_billing_email()`, `$order->get_total()`, `$order->get_status()` | `get_post_meta($order_id, '_billing_email', true)` |
| Write order field | `$order->set_status()` then `$order->save()` | Direct DB updates |
| Read order list | `wc_get_orders()` and `WC_Order_Query` | `WP_Query` with `post_type => 'shop_order'`, `get_posts()` against `shop_order` |
| Custom order data | `WC_Order::update_meta_data()` and `WC_Order::get_meta()` | `update_post_meta()` / `get_post_meta()` |

CRUD methods route through the active data store (HPOS or legacy) transparently. **Direct meta calls bypass HPOS entirely** and break under HPOS without compatibility mode.

### Migration Procedure

1. **Enable compatibility mode** (dual-write to both tables).
2. **Run synchronization** via WP-CLI: `wp wc hpos sync` for large stores.
3. **Verify data integrity**: `wp wc hpos verify_cot_data --verbose`.
4. **Test all critical flows**: checkout, refund, subscription renewal.
5. **Switch authoritative storage to HPOS**.
6. **Disable compatibility mode** only after confirming all plugins and custom code are HPOS-compatible.
7. **Keep a rollback path** by not deleting legacy data until confidence is established.

### Plugin Audit Before Migration

Audit all third-party plugins for HPOS compatibility before migration. The Plugins admin page with HPOS enabled flags incompatible plugins. Contact plugin vendors for HPOS-incompatible extensions and request updates. **If a critical plugin is incompatible, maintain compatibility mode (dual-write)** until the plugin updates, accepting the minor performance cost of writing to both storage backends.

---
[Back to Overview](./OVERVIEW.md)
