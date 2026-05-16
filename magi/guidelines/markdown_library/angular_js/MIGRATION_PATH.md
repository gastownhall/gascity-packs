# Migration Path to Modern Angular

### Migration Is Not Optional

AngularJS is end-of-life. Active migration is mandatory to avoid security and stability risks.

### Preparation Steps

1. **Adopt component architecture**: Replace controllers with `.component()`.
2. **Use one-way bindings**: Replace `=` with `<` except for form controls.
3. **Use lifecycle hooks**: Map constructor logic to `$onInit`, watchers to `$onChanges`, and teardown to `$onDestroy`.
4. **Introduce TypeScript**: Use `@types/angular` to enable incremental type safety.
5. **Eliminate `$scope` usage**: Inject `$scope` only for events or manual digest triggers.

### ngUpgrade Hybrid Strategy

Use `@angular/upgrade` to run both frameworks simultaneously:
- Migrate leaf components first.
- Work upward through the tree.
- Migrate shared services.
- Remove AngularJS bootstrap last.

### Migration Blockers

- `$rootScope` event broadcasting.
- Deep `$scope` inheritance.
- `$compile` for dynamic templates.
- jQuery DOM manipulation in controllers.

---
[Back to Overview](./OVERVIEW.md)
