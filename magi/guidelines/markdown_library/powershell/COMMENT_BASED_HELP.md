# Comment-Based Help

### Help Block Structure

Every public function requires a complete help block. Place immediately before the function or at the top of a script file.

```powershell
<#
.SYNOPSIS
    Brief one-line description of function purpose.
.DESCRIPTION
    Detailed explanation of what the function does, how it works, and when to use it.
    Multiple paragraphs are appropriate for complex functions. Include behavioral notes,
    limitations, and integration context.
.PARAMETER ParameterName
    Description of the parameter's purpose, acceptable values, and default behavior.
    One .PARAMETER block per parameter. Order matches parameter declaration order.
.INPUTS
    System.String
        Description of what can be piped to this function.
.OUTPUTS
    System.Management.Automation.PSCustomObject
        Description of what the function emits to the pipeline.
.EXAMPLE
    Get-ServiceStatus -Name 'W32Time'
    Retrieves the status of the Windows Time service.
.EXAMPLE
    'W32Time', 'BITS' | Get-ServiceStatus -Verbose
    Retrieves status for multiple services via pipeline input with verbose output.
.NOTES
    Author: Name
    Version: 1.0.0
    Requires: PowerShell 7.0 or later
.LINK
    https://docs.example.com/Get-ServiceStatus
.LINK
    Get-Service
#>
```

### Section Requirements

| Section | Rule |
|:--------|:-----|
| `.SYNOPSIS` | One line only, max 80 characters. Completes "This function will..." without stating "This function will." |
| `.DESCRIPTION` | Full explanation. Use cases, prerequisites, side effects, integration patterns. Multiple paragraphs for complex functions |
| `.PARAMETER` | One block per parameter. Describe purpose, constraints, defaults, relationships. Omit for common parameters (`-Verbose`, `-Debug`) |
| `.INPUTS` | Document types accepted via pipeline. Include `None` if pipeline input not supported |
| `.OUTPUTS` | Document types emitted to the pipeline. Include `None` for side-effect-only functions |
| `.EXAMPLE` | **Minimum two examples** for public functions. Each includes command, expected output/behavior, context |
| `.NOTES` | Author, version, change history, additional context |
| `.LINK` | Related commands and documentation URLs |

### Help Quality Standards

- Help must pass `Get-Help` rendering without warnings.
- Examples must be executable (syntactically correct, realistic parameters).
- Parameter descriptions must document validation constraints.
- Output types must match actual function behavior.

---
[Back to Overview](./OVERVIEW.md)
