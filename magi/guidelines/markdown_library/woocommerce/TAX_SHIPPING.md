# Tax and Shipping Configuration

Tax and shipping configuration affects order totals, compliance, and customer experience. **Misconfigured tax or shipping rules cause incorrect charges that erode trust and may violate tax collection obligations.**

### Tax Configuration

Configure tax based on the store's jurisdiction and nexus obligations. Enable taxes in WooCommerce > Settings > General. Configure tax rates in WooCommerce > Settings > Tax. **For U.S. stores with multi-state nexus, use an automated tax service** (WooCommerce Tax, TaxJar, Avalara) rather than manual rate tables. **Manual rate tables for jurisdiction-level U.S. tax are unmaintainable** — over 13,000 tax jurisdictions in the U.S. with rates that change quarterly.

### Tax-Inclusive vs Tax-Exclusive Pricing

**Configure prices as inclusive or exclusive of tax** (WooCommerce > Settings > Tax > Prices entered with tax) and **stick with one approach**. Switching after products are created requires recalculating all prices. Display prices including or excluding tax based on the customer's location and local regulations (e.g., **EU requires consumer-facing prices to include VAT**). The "Display prices in the shop" and "Display prices during cart and checkout" settings control this behavior independently.

### Tax in Headless

**For headless frontends, retrieve tax-inclusive/exclusive pricing from the Store API product response**, which respects the configured display settings based on the session's location context. **Do not calculate tax client-side.** Tax calculation involves jurisdiction lookup, product tax class matching, and exemption rules that must run through WooCommerce's tax engine server-side.

### Shipping Zones

**Configure shipping zones from most specific to least specific.** WooCommerce evaluates zones in order and assigns the first match. A "Rest of the World" zone catches addresses that do not match any specific zone. Within each zone, configure shipping methods (flat rate, free shipping, local pickup) with appropriate conditions and costs. **For real-time carrier rates, use carrier-specific plugins** (UPS, FedEx, USPS, DHL) that calculate rates via carrier APIs during checkout.

---
[Back to Overview](./OVERVIEW.md)
