# Template Patterns and Control Flow

### Built-in Control Flow

Angular 17+ introduces block-based control flow that replaces structural directives:

**Conditional rendering** with `@if`:
```html
@if (order(); as o) {
    <app-order-card [order]="o" />
} @else {
    <app-empty-state message="No order found" />
}
```

**Iteration** with `@for`:
```html
@for (item of items(); track item.id) {
    <app-list-item [data]="item" />
} @empty {
    <p>No items available</p>
}
```
The `track` expression is mandatory. Never track by index unless the collection is truly append-only and order-invariant.

**Pattern matching** with `@switch`:
```html
@switch (status()) {
    @case ('pending') { <app-pending-badge /> }
    @default { <span>Unknown</span> }
}
```

### Deferred Loading

`@defer` blocks enable template-level lazy loading with declarative trigger conditions:

```html
@defer (on viewport; prefetch on idle) {
    <app-heavy-chart [data]="chartData()" />
} @loading (minimum 200ms) {
    <app-skeleton-loader />
}
```

### Template Type Checking

Enable strict template type checking in `tsconfig.json`:

```json
{
    "angularCompilerOptions": {
        "strictTemplates": true,
        "strictInjectionParameters": true,
        "strictInputAccessModifiers": true
    }
}
```

### Pipe Usage

Pipes transform displayed values without mutating source data. Use pure pipes for deterministic transformations. Built-in pipes cover common cases; create custom pipes for domain-specific formatting. Impure pipes indicate misplaced logic that likely belongs in a service or computed signal.

### Template Reference Variables

Use `#ref` variables for template-local DOM references. Access them in event handlers, pass them to other components, or query them with `@ViewChild`.

---
[Back to Overview](./OVERVIEW.md)
