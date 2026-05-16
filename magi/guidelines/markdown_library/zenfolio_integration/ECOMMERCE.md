# E-Commerce and Cart Integration

Photography e-commerce integrations allow visitors to select photos from Zenfolio galleries and add them to a shopping cart for print ordering, digital download, or licensing. **The cart system bridges Zenfolio's gallery display with an external payment processor** (Stripe, WooCommerce, or Zenfolio's built-in selling features).

### Selection Tracking

**Track selected photos by their Zenfolio photo ID, not by URL or position.** Photo IDs are stable identifiers; URLs may change if images are re-processed; positions change if the gallery is reordered. Store in the cart for display and reference:

```ts
{ photoId, galleryId, title, thumbnailUrl }
```

**Retrieve pricing and product options from the commerce backend, not from Zenfolio.**

### Commerce Backend Integration

| Backend | Flow |
|:--------|:-----|
| **Zenfolio's built-in print selling** | Link to the photo's `PageUrl` for purchasing. Zenfolio handles the commerce flow |
| **External commerce system** | Cart collects photo selections and passes them to the external checkout (WooCommerce, Stripe Checkout Session) with **Zenfolio photo IDs as line item metadata**. The external system handles payment; fulfillment references the Zenfolio photo IDs |

### Selection UI

- Enable photo selection mode with a toggle.
- Selection mode adds checkboxes to each photo cell and a selection action bar (Select All, Clear Selection, Add to Cart).
- **Track selection state in a `Set`** for O(1) add/remove/check operations.
- Pass selection state to the parent component via an `onPhotosSelected` callback.

### Digital Download Delivery

For download purchases, use `GetDownloadOriginalKey` to generate **time-limited download tokens** for purchased photos. This method creates a key that grants temporary access to the original-resolution file. **The download key is generated server-side after payment confirmation** and provided to the customer via a secure download link. **Never generate download keys before payment is confirmed.**

---
[Back to Overview](./OVERVIEW.md)
