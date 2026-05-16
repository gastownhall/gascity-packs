# Component Architecture

### Component Hierarchy

| Class | Use |
|:------|:----|
| `WebPage` | Top-level container representing a complete HTML page |
| `Panel` | Reusable component with its own markup file — use for any UI fragment reused across pages |
| `Fragment` | Inline markup reuse within a single HTML file via `wicket:fragment` tags |
| `Border` | Wraps child markup with surrounding decoration |
| `WebMarkupContainer` | Generic container for grouping or adding behaviors |

### Component Lifecycle

Components progress through: Construction → `onInitialize` → `onConfigure` → `onBeforeRender` → Render → `onAfterRender` → `onDetach`.

| Hook | Required usage |
|:-----|:---------------|
| `onInitialize` | Add **all child components** here. The component is fully integrated into the hierarchy at this point. **Call `super.onInitialize()` first.** |
| `onConfigure` | Set visibility and enabled state here. Called every render cycle. **Never add or remove components in `onConfigure`.** |
| `onDetach` | Release expensive resources. **Always call `super.onDetach()` last** to ensure proper propagation to child components. |

### Markup Inheritance

Wicket supports markup inheritance parallel to Java class inheritance. Base page defines structure with `wicket:child` placeholder; child pages provide content via `wicket:extend` tags. The rendered output merges base and child markup seamlessly. Use for consistent layouts across page hierarchies.

---
[Back to Overview](./OVERVIEW.md)
