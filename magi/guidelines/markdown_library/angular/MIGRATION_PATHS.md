# Migration Paths

Migration from legacy Angular patterns is incremental. Mixing standalone and NgModule code is permitted during transition.

### Standalone Migration

1. Add `standalone: true` to components, directives, and pipes.
2. Move dependencies from NgModule declarations into the component `imports` array.
3. Remove migrated items from NgModule declarations.
4. Delete empty NgModules.

### Signal Migration (RxJS BehaviorSubject → Signal)

`BehaviorSubject` for synchronous state is an anti-pattern. Convert to signals at the service boundary.

```typescript
// Old
private dataSubject = new BehaviorSubject<Data[]>([]);
data$ = this.dataSubject.asObservable();

// New
private dataSignal = signal<Data[]>([]);
readonly data = this.dataSignal.asReadonly();
```

### Control Flow Migration

The official schematic migrates `*ngIf`, `*ngFor`, and `*ngSwitch` automatically:

```bash
ng generate @angular/core:control-flow
```

### Signal-Input/Output Migration

Replace decorator-based `@Input()`/`@Output()` with signal-based primitives:

```typescript
// Old
@Input() name!: string;
@Output() changed = new EventEmitter<void>();

// New
name = input.required<string>();
changed = output<void>();
```

### Zoneless Preparation

Migrate state to signals and eliminate zone.js triggers to prepare for zone-free operation.

---
[Back to Overview](./OVERVIEW.md)
