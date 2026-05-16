# UIKit Patterns

### View Controllers

- One responsibility per view controller; decompose into child view controllers for complex screens.
- Configure views in `viewDidLoad`; update data-driven UI in `viewWillAppear` or via bindings.
- **Avoid Massive View Controller syndrome.** Extract business logic to presenters, view models, or services.

### View Lifecycle

| Method | Purpose |
|:-------|:--------|
| `viewDidLoad` | One-time setup — subview creation, constraint installation, initial state |
| `viewWillAppear` / `viewDidAppear` | Refresh data, start animations, begin observing |
| `viewWillDisappear` / `viewDidDisappear` | Pause updates, stop animations, end observing |
| `deinit` | Verify deallocation; if it doesn't fire, find your retain cycle |

### Delegates and Data Sources

- Declare delegate properties as **`weak var`** — non-negotiable.
- Use protocol extensions to provide default implementations rather than optional methods.
- Consider **diffable data sources** (`UICollectionViewDiffableDataSource`) over traditional index-based approaches.

### Auto Layout

- Use programmatic constraints with layout anchors or a wrapper like SnapKit.
- Activate constraints in batches with `NSLayoutConstraint.activate()`.
- Set `translatesAutoresizingMaskIntoConstraints = false` on programmatically created views.
- Avoid ambiguous or conflicting constraints; run the layout debugger if warnings appear.

---
[Back to Overview](./OVERVIEW.md)
