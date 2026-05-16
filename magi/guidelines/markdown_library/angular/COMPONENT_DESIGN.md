# Component Design and Lifecycle

### Component Architecture

Components are the atomic unit of Angular's rendering model. Every component has exactly one responsibility: binding state to a template and forwarding user intent to services. Components do not fetch data, transform business objects, or orchestrate multi-step workflows.

### Standalone Component Structure

```typescript
@Component({
    selector: 'app-order-summary',
    standalone: true,
    imports: [CurrencyPipe, DatePipe, RouterLink],
    templateUrl: './order-summary.component.html',
    styleUrl: './order-summary.component.scss',
    changeDetection: ChangeDetectionStrategy.OnPush,
})
export class OrderSummaryComponent {
    order = input.required<Order>();
    cancel = output<string>();
}
```

### Change Detection Strategy

**OnPush is mandatory for all components.** Default change detection traverses the entire component tree on every event, timer, and HTTP response. OnPush restricts change detection to components whose inputs have changed by reference, whose signals have updated, or whose observables have emitted through the `async` pipe.

### Signal-Based Inputs and Outputs

Modern Angular replaces decorator-based `@Input()` and `@Output()` with signal-based equivalents:

- `input<T>()`: Optional input with signal semantics.
- `input.required<T>()`: Required input; template compiler enforces presence.
- `output<T>()`: Typed event emitter replacing `@Output() EventEmitter<T>`.
- `model<T>()`: Two-way bindable signal for parent-child state synchronization.

### Signal-Based Host Bindings

Use the `host` metadata field with signal-aware bindings instead of `@HostBinding`/`@HostListener`:

```typescript
@Component({
    selector: 'app-toggle',
    host: {
        '[class.active]': 'isActive()',
        '[attr.aria-pressed]': 'isActive()',
        '(click)': 'onClick($event)',
    },
})
```

### Lifecycle Hooks

- **constructor**: Inject dependencies only. Zero logic.
- **ngOnInit**: Initialize component state that depends on inputs. Trigger initial data loads through services.
- **ngOnDestroy**: Clean up subscriptions not managed by `async` pipe or `takeUntilDestroyed()`.
- **ngAfterViewInit**: Access `@ViewChild` references.

With signal-based inputs, `ngOnChanges` is unnecessary. Computed signals and effects replace the imperative change-tracking pattern entirely.

### Component Size Constraints

A component file should not exceed 150 lines including decorator metadata. If it does:
- Extract template logic into pipes or directives.
- Move data orchestration into a dedicated component-level service (facade).
- Split the template into child components.
- Move complex computed values into the service layer.

---
[Back to Overview](./OVERVIEW.md)
