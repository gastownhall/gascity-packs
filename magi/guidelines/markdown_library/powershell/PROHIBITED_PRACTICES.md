# Prohibited Practices

### Never Do

- Use `Invoke-Expression` with untrusted input — command injection vulnerability.
- Store credentials in plain text scripts or source control.
- Suppress all errors with `-ErrorAction SilentlyContinue` without handling them elsewhere.
- Use aliases in scripts — `gci`, `%`, `?` are unreadable and non-portable.
- Omit `[CmdletBinding()]` from functions — lose common parameter support.
- Use unapproved verbs — break discoverability and `Get-Command` integration.
- Write to host with `Write-Host` in functions that should emit pipeline output.
- Use `$global:` scope for function communication; pass parameters explicitly.
- Parse text output from commands — use native object properties.
- Ignore PowerShell version differences — test on target versions.
- Use `Exit` in functions — use `return` or `throw`.
- Leave `#Requires` statements out of scripts with dependencies.
- Use positional parameters beyond position 0 — name parameters explicitly.
- Create functions without comment-based help.
- Use `Read-Host` for credentials — use `Get-Credential`.
- Ignore `$PSCmdlet.ShouldProcess()` for state-changing operations.
- Use `Out-Null` when `[void]` cast is cleaner.
- Run shakedown against mocked cmdlets via `Mock`, in `ConstrainedLanguage` when production is `FullLanguage`, or under `$env:TEMP`/system temp paths.

---
[Back to Overview](./OVERVIEW.md)
