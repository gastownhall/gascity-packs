# Prohibited Practices (Absolute Blacklist)

### Never Do

- Write new features in AngularJS if a migration path exists.
- Use `$scope` directly in controllers (`controllerAs` mandatory).
- Use two-way binding (`=`) outside of form control wrappers.
- Register directives with `restrict: 'C'` or `restrict: 'M'`.
- Inject `$scope` into services or factories.
- Use `ng-controller` for inline controllers in templates.
- Perform DOM manipulation in controllers (use directives).
- Call `$http` directly from components/controllers (use services).
- Create deep `$watch` expressions on large objects.
- Disable SCE for convenience.
- Use `$compile` on user-supplied input.
- Suppress errors with empty `.catch()` blocks.
- Use implicit DI without `$inject` annotations.
- Store state in `$rootScope`.
- Use filters for array filtering in `ng-repeat` in production.
- Ignore `$destroy` events for cleanup.
- Reference `$scope.$parent` for communication.
- Use `angular.copy()` on large objects in hot paths.
- Use `$broadcast`/`$emit` as a general-purpose event bus.
- Use `$http.success()` or `.error()` (removed in 1.6).
- Mark filters as `$stateful = true`.
- Skip shakedown after touching core configurations.

---
[Back to Overview](./OVERVIEW.md)
