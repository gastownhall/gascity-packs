# SPA and Framework Integration

Single-page applications (Nuxt, Next.js, React, Angular, Vue) present unique challenges for session recording: route changes without page loads, dynamic DOM mutations, virtual DOM reconciliation, and client-side state management. The recording SDK must handle these correctly to produce coherent replays.

### Framework-Specific Initialization

| Framework | Initialization pattern |
|:----------|:-----------------------|
| Nuxt 3 | Client-only plugin (`.client.ts`) — initializes after consent verification and after the app mounts |
| Next.js | `useEffect` hook within a client component |
| React SPA | Top-level `useEffect` with empty dependency array |

The SDK must **initialize once and persist across SPA route changes**.

### SPA Route Detection

Verify the recording SDK captures SPA route changes. Most modern SDKs detect `pushState`/`replaceState` navigation automatically. **Test by navigating between routes and verifying the replay shows correct page transitions.** SDKs that do not detect SPA navigation produce replays where the entire session appears to happen on a single page.

### SSR/SSG Guards

For SSR/SSG frameworks, do **not** initialize the recording SDK on the server. The SDK requires a browser DOM. Guard initialization with framework-specific client-only mechanisms:

| Framework | Guard |
|:----------|:------|
| Nuxt | `import.meta.client` |
| Next.js | `typeof window !== 'undefined'` |
| Other | Framework-specific client-only mechanism |

Server-side initialization attempts cause errors or no-ops that may affect application stability.

### State Management Integration

Integrate recording with the application's state management for richer replay context:

| State manager | Plugin |
|:--------------|:-------|
| Redux | OpenReplay Redux plugin |
| Vuex / Pinia | OpenReplay Vue plugin |
| MobX | OpenReplay MobX plugin |
| NgRx | OpenReplay NgRx plugin |
| Zustand | OpenReplay Zustand plugin |

FullStory and LogRocket provide custom event APIs.

**State capture must not include sensitive state** (auth tokens, user PII in the store). Configure state capture to **exclude sensitive store slices**.

### Vue/Nuxt Component Annotation

For Nuxt/Vue applications, use OpenReplay's Vue plugin or FullStory's Vue integration for automatic component-level context in replays. These plugins annotate the replay with Vue component names, making it easier to identify which component rendered which content. Annotated replays reduce debugging time by providing component context without reading raw DOM.

---
[Back to Overview](./OVERVIEW.md)
