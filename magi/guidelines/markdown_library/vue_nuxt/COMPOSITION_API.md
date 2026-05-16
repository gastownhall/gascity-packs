# Vue 3 Composition API

### Script Setup Convention

Every single-file component uses `<script setup lang="ts">`. This is the only accepted script format for new components. Script setup provides compile-time macro support (`defineProps`, `defineEmits`, `defineExpose`, `defineOptions`, `defineSlots`, `defineModel`), automatic template binding of all top-level declarations, and optimal bundle size via eliminated boilerplate. Components that need explicit component options (`inheritAttrs`, `name` for recursive components) use `defineOptions()` within script setup.

### Reactivity Primitives

| Primitive | Use |
|:----------|:----|
| `ref()` | Default for primitives **and** single-value reactive references — works uniformly, requires explicit `.value` (reactivity is visible), survives destructuring |
| `reactive()` | Only when a complex object benefits from property-level access without `.value`; **destructuring breaks reactivity** |
| `computed()` | Derived values; must be **pure functions** of their reactive dependencies — no side effects in computed getters |
| `shallowRef()` | Large objects where deep reactivity is unnecessary and tracking only top-level replacement is sufficient |
| `toRef()` / `toRefs()` | Create reactive references from reactive object properties without breaking reactivity |
| `watch()` / `watchEffect()` | Side effects triggered by state changes; return a stop handle — store and call it during cleanup when created outside component setup |

### Composables

Composables are the primary abstraction for reusable stateful logic. Name with the `use` prefix: `useAuth`, `useCart`, `useFormValidation`. Return reactive state and methods as a plain object. Accept configuration via options objects, not positional parameters beyond the first required argument.

| Constraint | Required |
|:-----------|:---------|
| Naming | File name matches composable name: `composables/useAuth.ts` exports `useAuth()`. One primary composable per file |
| Lifecycle | Composables that register lifecycle hooks (`onMounted`, `onUnmounted`) must be called **synchronously** in setup — never inside async functions or after an `await` |
| Return type | Always a typed object. Return refs and computed values (not raw values) so consumers maintain reactivity |
| Cleanup | Side effects (event listeners, timers, subscriptions, WebSockets) must clean up in `onUnmounted` or via `watchEffect`'s `onCleanup` callback |

### Lifecycle Hooks

Use `onMounted()` for DOM access and browser-API initialization. Use `onUnmounted()` for cleanup. Use `onBeforeMount()` sparingly — server-side code in `setup()` or `useAsyncData` is almost always more appropriate. **In Nuxt SSR context, `onMounted` runs only on the client.** Code in `setup()` outside lifecycle hooks runs on both server and client. **Never access DOM elements in `setup` outside `onMounted`.**

### Template Refs

Type template refs with the element or component type:

```ts
const inputRef = ref<HTMLInputElement | null>(null)
```

Always check for null before accessing template ref values — the ref is null during SSR and before mount. For component refs, use `InstanceType<typeof MyComponent>` as the generic parameter. Use `useTemplateRef()` (Vue 3.5+) as the modern alternative that decouples the variable name from the template ref attribute.

### Provide/Inject

Use `provide`/`inject` for **dependency injection of services, configuration, and theme context** — not for application data flow. Define typed injection keys using `InjectionKey<T>` from Vue. Always provide a default value or throw an explicit error when injecting a required key, using `inject(key)` with a factory default or a dedicated `useRequiredInject` composable. Undocumented `inject` dependencies create invisible coupling that is impossible to trace without reading every ancestor's `provide` calls.

---
[Back to Overview](./OVERVIEW.md)
