# Required Practices

### Always Do

- Declare `#Requires` statements for version and module dependencies.
- Implement complete comment-based help for all public functions.
- Use `[CmdletBinding()]` and typed parameters.
- Apply validation attributes to parameters.
- Handle errors explicitly with `try`/`catch` and appropriate error actions.
- Support `-WhatIf` and `-Confirm` for destructive operations.
- Emit objects to the pipeline, not formatted strings.
- Use approved verbs from `Get-Verb`.
- Test with Pester — target 80%+ coverage.
- Use full cmdlet and parameter names; avoid aliases.
- Implement proper pipeline support with `begin`/`process`/`end`.
- Log with appropriate stream cmdlets (`Write-Verbose`, `Write-Warning`, `Write-Information`).
- Validate external input before use.
- Sign scripts for production deployment.
- Use secure credential storage; never embed secrets.
- Test cross-platform when targeting PowerShell 7+.
- Pass PSScriptAnalyzer with zero warnings.
- Run a §21 `Invoke-Shakedown` after every change touching integration boundaries.

---
[Back to Overview](./OVERVIEW.md)
