# Asset Management

### Enqueue Discipline

Register via `wp_register_script()` / `wp_register_style()` and enqueue in `wp_enqueue_scripts` (frontend) or `admin_enqueue_scripts` (admin). **Never output raw script/style tags in `wp_head` or `wp_footer`.** The enqueue system provides dependency resolution, cache-busting, conditional loading, and deduplication.

- Use `filemtime()` for versions during development.
- Use **build-generated hashes in production**.

**Load assets only on pages that need them.** Use `is_page()`, `is_singular()`, or custom conditions. **Plugin admin CSS has no business on frontend page loads.**

### Script Localization and Data Passing

Pass PHP data to JavaScript via `wp_localize_script()` or `wp_add_inline_script()` with `before` position. For REST API consumers, pass `rest_url()`, the nonce, and context-specific data through localization. **Never embed PHP variables directly in inline script tags.**

### Performance Budget

Every enqueued asset counts against the performance budget. Audit total assets per page load.

- Defer non-critical JavaScript (`strategy => defer` in WordPress 6.3+).
- Minify in the build pipeline.
- Conditionally load heavy libraries only when the page requires them.
- **Monitor Core Web Vitals impact of every plugin and theme asset addition.**

---
[Back to Overview](./OVERVIEW.md)
