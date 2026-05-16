# Hydration Safety

### Hydration Fundamentals

Hydration is the process where Vue attaches event listeners and reactivity to server-rendered HTML. The client-side virtual DOM must match the server-rendered DOM exactly. Mismatches cause Vue to discard the server HTML and re-render from scratch, producing visual flicker, destroying SEO benefits, and degrading performance. **Hydration mismatches are not warnings to ignore — they are bugs to fix.**

### Common Mismatch Causes and Solutions

Every hydration mismatch has a deterministic cause. Identify and eliminate the source rather than suppressing the warning.

| Cause | Solution |
|:------|:---------|
| Browser APIs in setup (`window`, `document`, `navigator`, `localStorage`, `sessionStorage`) | Guard with `import.meta.client` or move to `onMounted` |
| Date/time rendering (server timezone vs client timezone) | UTC formatting on the server; format to local time only inside `<ClientOnly>` or `onMounted` |
| Random values (IDs, keys, content during render) | Generate IDs in `useAsyncData` or `useState` so the value transfers via payload |
| Conditional rendering (`v-if` evaluated differently on server and client — screen width, feature detection, user agent) | `<ClientOnly>` for browser-dependent conditionals; initialize state server-side via `useState` |
| Third-party scripts modifying DOM before hydration (analytics, A/B tools, browser extensions) | Load via `useHead` with `defer`/`async`; inject after hydration via `onMounted` |
| HTML entity differences | Use Unicode characters directly rather than HTML entities in templates |

### ClientOnly Component

Wrap components that cannot render on the server in the built-in `<ClientOnly>` component. Provide a `#fallback` slot with a placeholder that matches the expected layout dimensions to prevent content layout shift during hydration. **`<ClientOnly>` is not a workaround for sloppy code** — it is for genuinely browser-dependent functionality (maps, canvas, WebGL, video players, authentication-gated widgets). If a component could render on the server but does not because of an avoidable browser API dependency, fix the component instead.

### useState for Hydration-Safe Shared State

Nuxt's `useState` composable creates SSR-friendly reactive state that serializes into the page payload and hydrates on the client without mismatch. Use `useState` for values that must be consistent between server and client render: user preferences, feature flags, locale, server-computed values referenced in multiple components. **`useState` keys must be unique strings.** Duplicate keys across different composables or components share state silently — namespace keys with the feature name.

---
[Back to Overview](./OVERVIEW.md)
