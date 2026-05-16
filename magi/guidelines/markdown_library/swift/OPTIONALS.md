# Optionals and Unwrapping

### Unwrapping Strategies

| Strategy | Use |
|:---------|:----|
| `guard let` | Early exit when the optional being nil means you cannot proceed |
| `if let` | Both the present and absent cases have meaningful work |
| `??` (nil-coalescing) | Provide a default value inline |
| `?.` (optional chaining) | Access nested optionals without intermediate unwrapping |

### Force Unwrapping

- **Prohibited in production code** except for IBOutlets (UIKit) and `@Environment` (SwiftUI) where the framework guarantees presence.
- If you reach for `!`, ask why the value is optional in the first place; **fix the model**.
- `fatalError` with a message is marginally better than `!` because it explains the invariant violation.

### Implicitly Unwrapped Optionals

- Use only for properties that are nil at init but **guaranteed initialized before use** (two-phase initialization).
- IBOutlets are the canonical example; avoid elsewhere.
- Prefer optional injection + `guard` over IUOs when feasible.

```swift
class ViewController: UIViewController {
    @IBOutlet weak var titleLabel: UILabel!  // Framework guarantees
    private var dataManager: DataManager!     // Set in viewDidLoad
    override func viewDidLoad() {
        super.viewDidLoad()
        dataManager = DataManager(context: self)
    }
}
```

### Optional Mapping

- Use `map` and `flatMap` on optionals to transform values without unpacking.
- Chain operations: `user.address?.city.map { $0.uppercased() }`.
- **Prefer `compactMap` over `map` + `filter`** for collections of optionals.

---
[Back to Overview](./OVERVIEW.md)
