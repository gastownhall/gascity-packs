# Style Summary

| Element | Required Style |
|:--------|:---------------|
| Architecture | Component-based (1.5+); feature-organized |
| Components | `.component()` for views; isolated scope; one-way bindings |
| Controllers | `controllerAs: 'vm'`; members at top; < 100 lines |
| Services | `.factory()` default; stateless preferred; return promises |
| Directives | Behavioral only (attribute restrict); cleanup on `$destroy` |
| DI | `$inject` annotation mandatory; `ng-strict-di` at bootstrap |
| Bindings | `<` for data input; `&` for callbacks; `=` for form controls only |
| Scope | Isolated scope ONLY; no inheritance chains; no `$rootScope` storage |
| Routing | `ui-router` with named states and resolve blocks |
| Forms | Named forms; `ng-model` for controls; validation on `$touched` |
| HTTP | Service-encapsulated; interceptors for auth/errors |
| Filters | Stateless pure functions; no `$stateful`; no array filtering in templates |
| Performance | Watcher budget < 2,000; one-time bindings; debug info disabled |
| Security | SCE enabled; no `$compile` on user input; CSP; pinned versions |
| Testing | Karma/Jasmine; `angular-mocks`; `$httpBackend`; 80% coverage |
| Migration | TS adoption; component architecture; one-way bindings |

---
[Back to Overview](./OVERVIEW.md)
