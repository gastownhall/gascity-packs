# Core Principles

These guidelines define strict, maintainable, and enterprise-ready patterns for all PowerShell development, optimizing for:

- **Verb-Noun Discipline** — Every function follows the approved verb taxonomy. Deviations break discoverability and violate the PowerShell contract with users.
- **Pipeline-First Design** — Functions accept pipeline input, emit typed objects, and compose naturally. String manipulation is the exception, not the rule.
- **Explicit Declaration** — Parameters, types, outputs, and requirements are declared, not inferred. Implicit behavior creates maintenance debt.
- **Defensive Execution** — Scripts validate preconditions, handle errors explicitly, and fail fast with actionable messages. Silent failures are organizational liabilities.
- **Cross-Platform Awareness** — PowerShell 7+ runs on Windows, Linux, and macOS. Platform-specific code is isolated and clearly marked.

### Primary Rule: PowerShell Is Not Batch Scripting

PowerShell operates on **objects**, not text streams. Functions emit structured data that downstream consumers can filter, transform, and aggregate without parsing. Treating PowerShell as a glorified batch interpreter — concatenating strings, parsing command output with regex, using exit codes for everything — wastes the platform's core value proposition. Design for the object pipeline from the start.

### Secondary Rule: Discoverability Is Non-Negotiable

`Get-Command`, `Get-Help`, and tab completion rely on consistent naming, comprehensive help blocks, and proper parameter declarations. A function without comment-based help, with cryptic parameter names, or using unapproved verbs is actively hostile to users. **Every public function must be discoverable through standard PowerShell mechanisms.**

### Version Strategy

Target PowerShell 7.x (LTS releases) for new development. PowerShell 5.1 compatibility is maintained only when organizational constraints require Windows PowerShell support.

```powershell
#Requires -Version 7.0
```

Windows-specific modules:

```powershell
#Requires -Version 5.1
#Requires -PSEdition Desktop
```

Cross-platform modules:

```powershell
#Requires -Version 7.0
#Requires -PSEdition Core
```

---
[Back to Overview](./OVERVIEW.md)
