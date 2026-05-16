# Advanced Patterns

### Custom Property Wrappers

```swift
@propertyWrapper
struct Clamped<Value: Comparable> {
    private var value: Value
    private let range: ClosedRange<Value>

    var wrappedValue: Value {
        get { value }
        set { value = min(max(range.lowerBound, newValue), range.upperBound) }
    }

    init(wrappedValue: Value, _ range: ClosedRange<Value>) {
        self.range = range
        self.value = min(max(range.lowerBound, wrappedValue), range.upperBound)
    }
}

struct Settings {
    @Clamped(0...100) var volume: Int = 50
    @Clamped(0.0...1.0) var brightness: Double = 0.5
}
```

### Result Builders

```swift
@resultBuilder
struct AttributedStringBuilder {
    static func buildBlock(_ components: AttributedString...) -> AttributedString {
        components.reduce(into: AttributedString()) { $0 += $1 }
    }
    static func buildOptional(_ component: AttributedString?) -> AttributedString {
        component ?? AttributedString()
    }
    static func buildEither(first: AttributedString) -> AttributedString { first }
    static func buildEither(second: AttributedString) -> AttributedString { second }
}
```

Use result builders for domain-specific languages.

### Phantom Types

Use phantom types for compile-time safety without runtime cost:

```swift
struct Distance<Unit> {
    let value: Double
}
enum Meters {}
enum Feet {}

extension Distance where Unit == Meters {
    func toFeet() -> Distance<Feet> {
        Distance<Feet>(value: value * 3.28084)
    }
}
```

The compiler enforces unit correctness at the type level — `Distance<Meters>` and `Distance<Feet>` are distinct types that cannot be accidentally mixed.

---
[Back to Overview](./OVERVIEW.md)
