# Email and Notification Management

WooCommerce sends transactional emails at key order lifecycle points. These emails are triggered by hooks, rendered via templates, and dispatched via the WordPress mailer (`wp_mail`).

### Transactional Email Service

**Configure a transactional email service** (SendGrid, Postmark, SES, Mailgun) via an SMTP plugin or API-based sending plugin **rather than relying on the server's built-in `mail()` function**. PHP `mail()` is unreliable, unmonitorable, and frequently blocked by hosting providers. SPF, DKIM, and DMARC alignment require control over the sending infrastructure that PHP `mail()` does not provide.

### Template Customization

Customize email templates via the WooCommerce template override system: **copy the template** from `woocommerce/templates/emails/` to `your-theme/woocommerce/emails/` and modify the copy. **Do not edit plugin templates directly** — updates overwrite changes. For headless architectures where WooCommerce's PHP-rendered email templates are not used, replace WooCommerce's email dispatch with custom notification logic (triggered by the same hooks) that renders templates appropriate to the frontend stack.

### Disabling Irrelevant Emails

Disable email notifications that are not relevant to the store's workflow. WooCommerce sends emails for: new order (admin), cancelled order (admin), failed order (admin), order on-hold, processing, completed, refunded, customer note. **For headless stores with custom notification systems, selectively disable WooCommerce's built-in emails** in WooCommerce > Settings > Emails to prevent duplicate notifications.

---
[Back to Overview](./OVERVIEW.md)
