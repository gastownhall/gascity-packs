# Swift Package Manager

### Package Structure

```swift
// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "MyLibrary",
    platforms: [
        .iOS(.v15),
        .macOS(.v12)
    ],
    products: [
        .library(name: "MyLibrary", targets: ["MyLibrary"])
    ],
    dependencies: [
        .package(url: "https://github.com/apple/swift-algorithms", from: "1.0.0")
    ],
    targets: [
        .target(
            name: "MyLibrary",
            dependencies: [
                .product(name: "Algorithms", package: "swift-algorithms")
            ]
        ),
        .testTarget(
            name: "MyLibraryTests",
            dependencies: ["MyLibrary"]
        )
    ]
)
```

- Define `Package.swift` with **explicit dependencies**.
- Use **semantic versioning** for releases.
- Specify minimum platform versions.

### Modular Design

- Separate features into packages.
- Shared utilities in a `Core` package.
- Use protocols at module boundaries for dependency injection.

---
[Back to Overview](./OVERVIEW.md)
