# Naming Conventions

### Verb-Noun Function Names

All functions use Verb-Noun format with approved verbs from `Get-Verb`:

| Category | Verbs |
|:---------|:------|
| Data | `Get`, `Set`, `Add`, `Remove`, `Clear`, `Find`, `Search`, `Select` |
| Lifecycle | `New`, `Start`, `Stop`, `Restart`, `Enable`, `Disable`, `Initialize` |
| Communication | `Connect`, `Disconnect`, `Send`, `Receive`, `Read`, `Write` |
| Diagnostic | `Test`, `Debug`, `Trace`, `Measure`, `Assert`, `Compare` |
| Security | `Grant`, `Revoke`, `Protect`, `Unprotect`, `Block`, `Unblock` |

Verify verb approval:

```powershell
Get-Verb | Where-Object Verb -eq 'YourVerb'
```

### Noun Guidelines

- Singular nouns for functions operating on single items: `Get-User`, not `Get-Users`.
- Prefix with module or product identifier for disambiguation: `Get-AzStorageAccount`, `Get-ADUser`.
- PascalCase for compound nouns: `Get-NetworkAdapter`, not `Get-networkadapter`.
- Avoid abbreviations unless universally understood: `VM` acceptable, `Cfg` not.

### Variable Naming

| Scope | Style |
|:------|:------|
| Script-scoped variables and parameters | `$PascalCase` |
| Local variables | `$camelCase` |
| Forbidden | `$SCREAMING_SNAKE_CASE`, `$snake_case` |
| Emphasis | Use `$script:ModuleConfig` instead of all-caps |

Descriptive names over abbreviations: `$processedItems`, not `$pi`.

### Parameter Naming

- PascalCase matching established patterns: `-ComputerName`, not `-Computername` or `-computer_name`.
- Match parameter names from related cmdlets: if `Get-Process` uses `-Name`, your process-related function uses `-Name`.
- Boolean parameters become switches: `-Force`, `-PassThru`, `-WhatIf`. Never `-IsForced $true`.

### Private Function Naming

Internal helper functions not exported from modules:

- Prefix with module identifier to prevent collisions: `ModuleName_HelperFunction`.
- Or use explicit `private` scope designation.
- Document as private; omit from module exports.

---
[Back to Overview](./OVERVIEW.md)
