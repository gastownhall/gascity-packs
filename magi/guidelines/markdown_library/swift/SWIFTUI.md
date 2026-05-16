# SwiftUI Patterns

### View Composition

- Keep views small and focused; **extract subviews liberally**.
- Use computed properties for static subview extraction; use `@ViewBuilder` methods for dynamic construction.
- Prefer custom view types over deeply nested inline views.
- Name extracted views descriptively: `UserAvatarView`, `PrimaryActionButton`.

### State Management

| Wrapper | Purpose |
|:--------|:--------|
| `@State` | Private, view-local state owned by the view |
| `@Binding` | Two-way reference to state owned by a parent |
| `@StateObject` | View-owned reference type lifecycle; use for view models |
| `@ObservedObject` | Reference type observed but not owned; parent passes it in |
| `@EnvironmentObject` | Dependency-injected observable from the environment |
| `@Environment` | Framework-provided values (color scheme, locale, dismiss action) |

### Observable Macro (Swift 5.9+)

Use `@Observable` macro on classes instead of `ObservableObject` for simpler observation with finer-grained updates:

```swift
@Observable
final class Model {
    var count = 0
    var name = ""
}

struct ContentView: View {
    @Bindable var model: Model
    var body: some View {
        TextField("Name", text: $model.name)
        Text("Count: \(model.count)")
    }
}
```

- Access properties directly; no `@Published` wrappers needed.
- Use `@Bindable` for bindings to `@Observable` objects in SwiftUI views.

### Performance

- Use `EquatableView` or custom `Equatable` conformance to prevent unnecessary redraws.
- Avoid expensive computations in view bodies; move to view models or use `task` modifier.
- Use `LazyVStack`/`LazyHStack` for long lists; **never use plain `VStack` for unbounded data**.
- Profile with Instruments; do not guess at rendering bottlenecks.

### Navigation

- Use `NavigationStack` (iOS 16+) with **value-based navigation** for type-safe routing.
- Define navigation destinations with `navigationDestination(for:)` at the appropriate scope.
- Avoid deprecated `NavigationLink` patterns without explicit values.

### SwiftUI vs UIKit Decision

| Question | Answer |
|:---------|:-------|
| Minimum iOS version 14+? | Yes → consider SwiftUI; No → UIKit |
| Need complex animations or gestures? | Yes → consider UIKit or hybrid |
| Heavy custom drawing? | Yes → UIKit with Core Graphics; No → SwiftUI Canvas or shapes |

---
[Back to Overview](./OVERVIEW.md)
