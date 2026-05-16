# Script Structure and Requirements

### Requires Statements

Every script begins with `#Requires` statements. **PowerShell enforces them before script execution begins** — they are not comments.

```powershell
#Requires -Version 7.0
#Requires -Modules @{ ModuleName = 'Az.Accounts'; ModuleVersion = '2.0.0' }
#Requires -Modules @{ ModuleName = 'Az.Resources'; RequiredVersion = '6.5.0' }
#Requires -RunAsAdministrator
#Requires -PSEdition Core
```

| Statement | Purpose |
|:----------|:--------|
| `-Version` | Minimum PowerShell version |
| `-Modules` | Module dependencies with version constraints |
| `-RunAsAdministrator` | Require elevation |
| `-PSEdition` | Constrain to `Desktop` (Windows PowerShell) or `Core` (PowerShell 7+) |

### Script File Organization

| Order | Element |
|:-----:|:--------|
| 1 | `#Requires` statements |
| 2 | Comment-based help block |
| 3 | `[CmdletBinding()]` and `param()` block |
| 4 | `using` statements for namespaces and modules |
| 5 | Script-scoped variables and constants |
| 6 | Private helper functions |
| 7 | Main logic in `begin`/`process`/`end` blocks or after function definitions |

### Using Statements

`using` statements appear at the top of the script, after `#Requires` but before any other code:

```powershell
#Requires -Version 7.0
using namespace System.Collections.Generic
using namespace System.Management.Automation
using module Az.Accounts
```

### Strict Mode

```powershell
Set-StrictMode -Version Latest
```

Strict mode prevents:

- References to uninitialized variables.
- References to non-existent properties.
- Calling functions using method syntax with incorrect arguments.
- Variable expansion in strings that reference undefined variables.

Enable in development and testing. Consider deployment implications — strict mode can break scripts that relied on lenient behavior.

### Encoding and Line Endings

| Constraint | Detail |
|:-----------|:-------|
| Encoding (Windows PowerShell) | UTF-8 with BOM |
| Encoding (PowerShell 7+ cross-platform) | UTF-8 without BOM |
| Line endings (cross-platform) | LF |
| Line endings (Windows-only) | CRLF acceptable |
| Trailing whitespace | None on any line |

---
[Back to Overview](./OVERVIEW.md)
