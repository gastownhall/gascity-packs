# Project Structure and Organization

### Standard Directory Layout

```text
Project/
├── Package.swift (SPM) or Project.xcodeproj
├── Sources/
│   ├── App/
│   │   ├── AppDelegate.swift (UIKit) or App.swift (SwiftUI)
│   │   ├── SceneDelegate.swift (UIKit, if applicable)
│   │   └── Configuration/
│   ├── Features/
│   │   ├── Authentication/
│   │   │   ├── AuthenticationView.swift
│   │   │   ├── AuthenticationViewModel.swift
│   │   │   └── AuthenticationService.swift
│   │   └── Dashboard/
│   ├── Core/
│   │   ├── Networking/
│   │   ├── Persistence/
│   │   └── Extensions/
│   ├── Models/
│   │   ├── User.swift
│   │   └── DTOs/
│   └── Utilities/
├── Tests/
│   ├── UnitTests/
│   └── IntegrationTests/
└── Resources/
    ├── Assets.xcassets
    └── Localizable.strings
```

### File Organization Rules

- One primary type per file; file name matches the type name exactly.
- Extensions implementing protocol conformance may reside in separate files named `TypeName+ProtocolName.swift`.
- Related small types (under 50 lines combined) may cohabitate in a single file.
- Feature modules are self-contained: view, view model, service, and models grouped together.
- Shared utilities live in `Core/` or `Utilities/`; never scatter helpers across feature directories.

### Within-File Organization

1. Import statements (Foundation/UIKit/SwiftUI first, then third-party, then internal).
2. Type declaration with properties (constants before variables, static before instance).
3. Initializers.
4. Protocol conformances in extensions (one extension per protocol).
5. Private helpers in a `private extension` block.

---
[Back to Overview](./OVERVIEW.md)
