# Style Summary

| Element | Required pattern |
|:--------|:-----------------|
| **Models** | `LoadableDetachableModel` for database data; `PropertyModel` for property binding; `CompoundPropertyModel` for forms; never raw objects |
| **Components** | Add children in `onInitialize()`; configure visibility in `onConfigure()`; release resources in `onDetach()`; always call super methods |
| **Templates** | Valid HTML; wicket namespace declared; meaningful placeholder content; no logic in markup; `wicket:id` matches Java component ID |
| **Forms** | `CompoundPropertyModel` binding; server-side validation mandatory; `FeedbackPanel` for messages; proper error handling |
| **Ajax** | `setOutputMarkupId(true)` on targets; throttle rapid events; use `AjaxFallbackLink` for graceful degradation |
| **Sessions** | Store IDs not entities; call `dirty()` after modifications; minimize session size; use stateless pages where possible |
| **Serialization** | All fields serializable or transient; use detachable models; avoid capturing outer references in anonymous classes |
| **Security** | CSRF protection enabled; CSP headers configured; input validated server-side; output encoded by default |
| **Resources** | Package with component; contribute via `renderHead()`; bundle for production; deduplicate automatically |
| **Testing** | `WicketTester` for all pages/panels; `FormTester` for forms; mock services via DI; verify error handling |
| **DI** | `@SpringBean` or `@Inject` for services; never instantiate services directly; beans inject as serializable proxies |
| **Performance** | `DataView` with pagination for large lists; lazy load heavy panels; minimize component tree depth |
| **i18n** | Resource bundles from start; `StringResourceModel` with parameters; locale via session |
| **Shakedown** | Real servlet container only; six validation categories; pass/fail-blocking/fail-nonblocking/inconclusive; four required artifacts |
| **Defense in Depth** | Typed models + WicketTester + session discipline + E2E browser + Ajax error paths + monitoring + upgrade discipline = seven independent layers; WicketTester + E2E + telemetry = the Rule of Three quorum |

---

**Apply these guidelines universally to all Apache Wicket development.**

---
[Back to Overview](./OVERVIEW.md)
