# Theme and Page Builder Interoperability

### Child Theme Discipline

**Never modify parent theme files.** All customizations go in the child theme. The child theme `functions.php` loads after the parent, allowing filter overrides and action additions. Enqueue child styles with the parent style as a dependency. Store template overrides using the same relative path as the parent. **When the parent updates, child overrides persist.**

### Avada Theme Integration

Avada uses a proprietary element system (Fusion Builder). Custom elements integrate through `fusion_builder_map()`. Avada Global Options stores configuration in the theme options. Override templates by copying to the child theme `templates/` directory. **Avada's dynamic CSS regenerates on option save** — flush the CSS cache after programmatic option changes. Avoid library conflicts with Avada's bundled dependencies (jQuery UI, FontAwesome, Select2) by checking enqueue state before registering.

| Constraint | Detail |
|:-----------|:-------|
| Performance | Avada CSS/JS concatenation can conflict with external optimization plugins. **Use either Avada's built-in performance features or an external plugin, not both** |
| Compatibility | **Avada internal APIs change between major versions without deprecation.** Pin the version and test updates in staging before production |

### Elementor Integration

Elementor widgets extend `\Elementor\Widget_Base`. Register custom widgets in `elementor/widgets/register`. **Elementor stores page content as serialized post meta (`_elementor_data`), not in `post_content`.** Standard WordPress content filters do not apply to Elementor-rendered pages. Use `elementor/frontend/after_enqueue_styles` and `elementor/frontend/after_enqueue_scripts` for conditional asset loading.

| Constraint | Detail |
|:-----------|:-------|
| Rendering | Content editable in Elementor is not editable in the block editor simultaneously. **Decide per-page which editor owns content and enforce that decision** |
| Dynamic tags | Elementor Pro dynamic tags pull from post meta, ACF fields, and custom sources. Register custom dynamic tags by extending the base Tag class for maintainability |
| Caching | Elementor generates CSS per page. **Clear the CSS cache after theme changes, font updates, or breakpoint modifications.** Automate cache clearing in deployment pipelines |

### Block Editor Coexistence

Sites running page builders may still use the block editor for specific post types. **Disable the block editor selectively** via `use_block_editor_for_post_type` filter. Register custom block patterns and templates for post types that use it. Ensure block styles do not conflict with builder output. **Use `theme.json` for block editor configuration** to maintain design consistency.

---
[Back to Overview](./OVERVIEW.md)
