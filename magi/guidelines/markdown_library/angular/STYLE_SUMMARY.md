# Style Summary

| Element | Required Style |
|:--------|:---------------|
| Components | Standalone; OnPush; signal inputs/outputs; < 150 lines |
| Templates | Built-in control flow (@if, @for, etc.); @defer; strict checking |
| Change Detection | OnPush mandatory; zoneless target; signal-driven |
| State | Component-level signals; service-level readonly signals; SignalStore |
| RxJS | Async streams ONLY; correct flattening operators; no managed subs |
| Subscriptions | `async` pipe, `toSignal()`, or `takeUntilDestroyed()` |
| Routing | Lazy loaded; functional guards/resolvers; input binding |
| Forms | Typed reactive forms; `NonNullableFormBuilder`; zod validation |
| HTTP | Service-encapsulated; functional interceptors; schema validation |
| DI | `inject()` function; route-level for feature scope |
| Host bindings | Signal-aware `host` metadata; no @HostBinding/@HostListener |
| SSR / Hydration | `provideClientHydration` with event replay |
| Security | Sanitization; CSRF; tokens in HTTP-only cookies; CSP |
| Performance | Lazy loading; @defer; virtual scrolling; `NgOptimizedImage` |
| Testing | 80%+ coverage; signals tested synchronously; HTTP mocked |
| Build | AOT; strict mode; zero warnings; bundle budgets |
| Shakedown | Production bundle + real backend + Playwright smoke |
| Migration | Schematic for control flow; BehaviorSubject → signal |
| Defense in Depth | Strict TS + lint + units + zod + AOT + shakedown |
| File Structure | Feature-based directories; core/shared/features separation |

---
[Back to Overview](./OVERVIEW.md)
