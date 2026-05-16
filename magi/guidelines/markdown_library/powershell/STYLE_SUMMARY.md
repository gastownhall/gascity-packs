# Style Summary

| Element | Required Style |
|:--------|:---------------|
| Version Declaration | `#Requires -Version 7.0` at script start |
| Module Dependencies | `#Requires -Modules` with version constraints |
| Function Naming | Verb-Noun with approved verbs from `Get-Verb` |
| Parameter Declaration | `[CmdletBinding()]` with typed, validated parameters |
| Comment-Based Help | Complete `.SYNOPSIS`, `.DESCRIPTION`, `.PARAMETER`, `.EXAMPLE` |
| Error Handling | `$ErrorActionPreference = 'Stop'` with explicit `try`/`catch` |
| Output | Typed objects via `[OutputType()]`; emit to pipeline |
| Pipeline Support | `begin`/`process`/`end` blocks; `ValueFromPipeline` parameters |
| State Changes | `SupportsShouldProcess` with `-WhatIf` / `-Confirm` |
| Credential Handling | `[PSCredential]` type; `SecretManagement` for vault-backed access; never plain text |
| Logging | `Write-Verbose`, `Write-Warning`, `Write-Information` with tags; Start-Transcript for runs |
| Testing | Pester 5.x; mocks for isolation; 80%+ coverage |
| Remote Execution | `Invoke-Command` with explicit credentials and throttling |
| Performance | Generic collections over arrays; hashtable lookups over `Where-Object` |
| Cross-Platform | `$IsWindows` / `$IsLinux` / `$IsMacOS` detection; `[IO.Path]` for paths |
| Module Structure | Manifest + root module + Public/Private folders |
| Parallelism | `ForEach-Object -Parallel` with `-ThrottleLimit` |
| Script Signing | Code signing certificates for production |
| Lint | `Invoke-ScriptAnalyzer -Settings PSGallery -Severity Error,Warning` zero violations |
| DSC | Resources packaged as modules; configuration data separation |
| PowerShell 7+ | `??`, `??=`, ternary, `&&`/`||` chain operators where supported |
| Shakedown | `Invoke-Shakedown` with real providers and Start-Transcript artifact; classify Pass / FailBlocking / FailNonBlocking / Inconclusive |
| Defense in Depth | Strict mode + PSScriptAnalyzer + SupportsShouldProcess + Pester + transcript + retry/timeout + shakedown |
| Rule of Three | Exit status + transcript content + post-condition `Get-*` check MUST agree before declaring success |

---
[Back to Overview](./OVERVIEW.md)
