# PCI DSS and Payment Page Handling

Session recording on pages that contain payment forms introduces PCI DSS scope. Even when payment fields are rendered in Stripe Elements or PayPal hosted iframes (which the recording SDK cannot read into due to cross-origin restrictions), the surrounding page context, form layout, and user interactions may contain information that PCI assessors evaluate.

### Default Posture: Exclude Payment Pages

Do **not** record sessions on payment pages that contain payment card data entry, even if the card fields are in an iframe. The recording SDK captures the surrounding page DOM, which may include cardholder name, billing address, and other PCI-relevant fields. The safest approach is to **exclude payment pages from recording entirely** via route-based exclusion or by calling the SDK's stop method when the user enters the payment flow.

### If Recording Is Required on Payment Pages

If recording on payment pages is a business requirement (debugging checkout drop-off):

1. **Mask every element** on the page.
2. Selectively unmask only non-sensitive layout elements (buttons, progress indicators, step labels).
3. Verify with the **PCI QSA** that the recording configuration does not expand PCI scope.
4. Document the masking configuration and the QSA's assessment in the compliance record.

### Keystroke Capture on Payment Pages

**Never record keystrokes on payment pages.** Keystroke recording captures characters typed into card number, CVV, and expiration fields **regardless of visual masking**. Configure the SDK to disable keystroke capture on payment routes:

| SDK | Configuration |
|:----|:--------------|
| OpenReplay | `obscureInputEmails`, `obscureInputDates`, per-input obscuring |
| FullStory | Private by Default blocks all input capture |

Verify no keystroke data for payment fields appears in recorded sessions.

---
[Back to Overview](./OVERVIEW.md)
