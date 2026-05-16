# Shakedown — Integration Validation

### Definition

A shakedown is the **first controlled end-to-end execution of a PowerShell script, module, or advanced function against real cmdlet providers, PSDrives, and remoting endpoints** after any change that touches integration boundaries. Shakedown exercises the actual pipeline, parameter set resolution, module graph, and error record propagation that the code uses in production.

It is **not** Pester unit testing and **not** static parameter validation.

### Shakedown vs Preflight vs Pester

| Phase | Question Answered |
|:------|:------------------|
| Preflight | Static prerequisites — `[ValidateScript]`, `[ValidatePattern]`, etc. |
| **Shakedown** | **Full advanced function with Begin/Process/End executes against real cmdlet dependencies — integration soundness** |
| Pester | Behavioral and unit verification at scale |

### Mandatory Triggers

Shakedown is mandatory after any of:

- New advanced function or cmdlet.
- Module manifest (`.psd1`) `RequiredModules` or `NestedModules` change.
- Parameter set redesign or `ValueFromPipeline` change.
- `ErrorAction`, `ErrorVariable`, or `$ErrorActionPreference` handling change.
- New `Import-Module` dependency or dependency version bump.
- New PSDrive provider usage (`FileSystem`, `Registry`, `Certificate`, `WSMan`).
- Remoting session change (`New-PSSession`, `Invoke-Command`, CredSSP, JEA).
- Upgrade from Windows PowerShell 5.1 to PowerShell 7.x.

### Non-Triggers

- Comment-based help edits.
- `Write-Verbose` message rewording.
- Formatting/style changes governed by PSScriptAnalyzer.
- Changes to values in a validated parameter schema.

### Validation Categories

1. **Pipeline integrity** — objects flow through Begin/Process/End correctly; `ValueFromPipeline` and `ValueFromPipelineByPropertyName` bind expected properties; downstream cmdlets receive expected object types; no silent string coercion at pipeline boundaries.
2. **Cmdlet/module state** — cmdlets and modules load, exported commands resolve, module-scoped variables initialize, required .NET types load from assemblies, class definitions instantiate.
3. **Parameter sets** — intended parameter set resolves for each supported call pattern; mutually exclusive sets remain mutually exclusive; dynamic parameters appear when their conditions are met.
4. **Module graph** — `Import-Module` resolves all `RequiredModules` and `NestedModules` at declared versions; no assembly load conflicts; no shadowed cmdlets from conflicting modules.
5. **PSDrive availability** — required PSDrive providers present; paths resolve with expected semantics; `Get-Item`/`Set-Item` round-trip against the intended provider, not a coincidentally-named FileSystem path.
6. **Remoting sessions** — `New-PSSession` connects with intended authentication; `Invoke-Command` executes in target runspace; session state propagates; sessions close cleanly.
7. **Error record propagation** — terminating errors surface via `throw` and `trap`; non-terminating errors populate `$Error` and respect `-ErrorAction`; `-ErrorVariable` captures expected `ErrorRecord`; `try/catch/finally` executes cleanup reliably.

### Execution Principles

- Use **representative safe inputs** — not adversarial or stress inputs.
- Run against a sandbox PSDrive, test remoting endpoint, or scratch directory — **never production**.
- Enable `-Verbose` and `-Debug` on the code under shakedown.
- `Start-Transcript` captures the full session output as an execution artifact.
- Start with the simplest end-to-end call pattern, then add parameter sets incrementally.
- Do not optimize during shakedown — emit a `Write-Warning` and continue.

### Invoke-Shakedown Pattern

```powershell
function Invoke-Shakedown {
    [CmdletBinding(DefaultParameterSetName = 'Default', SupportsShouldProcess = $true)]
    [OutputType([pscustomobject])]
    param(
        [Parameter(ParameterSetName = 'Default', Position = 0, ValueFromPipeline = $true)]
        [ValidateNotNullOrEmpty()]
        [string] $ModuleName,

        [Parameter(ParameterSetName = 'Default')]
        [ValidateScript({ Test-Path -LiteralPath $_ -PathType Container })]
        [string] $ScratchRoot = (Join-Path -Path $PSScriptRoot -ChildPath '.shakedown'),

        [Parameter(ParameterSetName = 'Default')]
        [switch] $IncludeRemoting
    )
    begin {
        $results = [System.Collections.Generic.List[pscustomobject]]::new()
        if (-not (Test-Path -LiteralPath $ScratchRoot)) {
            New-Item -ItemType Directory -Path $ScratchRoot -Force | Out-Null
        }
        $transcript = Join-Path -Path $ScratchRoot -ChildPath ("shakedown-{0:yyyyMMdd-HHmmss}.log" -f [datetime]::UtcNow)
        Start-Transcript -Path $transcript -Force | Out-Null
    }
    process {
        if (-not $PSCmdlet.ShouldProcess($ModuleName, 'Shakedown')) { return }

        # 1. Pipeline integrity
        $pipelineOk = $false
        try {
            $piped = 'fixture' | ForEach-Object { [pscustomobject]@{ Value = $_ } }
            $pipelineOk = $piped -and $piped.Value -eq 'fixture'
        } catch { $pipelineOk = $false }
        $results.Add([pscustomobject]@{ Category = 'PipelineIntegrity'; Pass = $pipelineOk })

        # 2. Cmdlet/module state
        $moduleOk = $null -ne (Get-Module -Name $ModuleName -ListAvailable -ErrorAction SilentlyContinue)
        $results.Add([pscustomobject]@{ Category = 'ModuleState'; Pass = $moduleOk })

        # 3. Parameter set resolution
        $paramOk = $true
        try { Get-Command -Module $ModuleName -ErrorAction Stop | Out-Null } catch { $paramOk = $false }
        $results.Add([pscustomobject]@{ Category = 'ParameterSets'; Pass = $paramOk })

        # 4. PSDrive availability
        $driveOk = $null -ne (Get-PSDrive -Name 'FileSystem' -ErrorAction SilentlyContinue)
        $results.Add([pscustomobject]@{ Category = 'PSDrive'; Pass = $driveOk })

        # 5. Error record propagation
        $errorOk = $false
        try {
            $ErrorActionPreference = 'Stop'
            try { Get-Item -LiteralPath (Join-Path $ScratchRoot 'nonexistent.xyz') -ErrorAction Stop }
            catch { $errorOk = $_ -is [System.Management.Automation.ErrorRecord] }
        } finally { $ErrorActionPreference = 'Continue' }
        $results.Add([pscustomobject]@{ Category = 'ErrorPropagation'; Pass = $errorOk })

        # 6. Remoting session state (opt-in)
        if ($IncludeRemoting) {
            $remotingOk = $false
            try {
                $session = New-PSSession -ComputerName 'localhost' -ErrorAction Stop
                Invoke-Command -Session $session -ScriptBlock { $PSVersionTable.PSEdition } | Out-Null
                Remove-PSSession -Session $session
                $remotingOk = $true
            } catch { $remotingOk = $false }
            $results.Add([pscustomobject]@{ Category = 'Remoting'; Pass = $remotingOk })
        }
    }
    end {
        Stop-Transcript | Out-Null
        $failed = @($results | Where-Object { -not $_.Pass })
        $classification = if ($failed.Count -eq 0) { 'Pass' } else { 'FailBlocking' }
        [pscustomobject]@{
            Classification = $classification
            Results        = $results
            Transcript     = $transcript
            Timestamp      = [datetime]::UtcNow
        }
    }
}
```

### Result Classification

`Invoke-Shakedown` emits a `pscustomobject` with a `Classification` field:

| Value | Meaning |
|:------|:--------|
| `Pass` | All validation categories succeeded |
| `FailBlocking` | At least one category failed in a way that prevents correct operation — fix before proceeding |
| `FailNonBlocking` | Non-critical anomaly observed — log to issue tracker and proceed with caution |
| `Inconclusive` | Environment or input limitations prevented validation — adjust and re-run |

### Required Artifacts

Every `Invoke-Shakedown` run produces four artifacts in the scratch directory:

- The `Start-Transcript` execution log.
- A result summary per validation category.
- An issue list of observed anomalies.
- An environment snapshot containing `$PSVersionTable`, `Get-Module -ListAvailable`, and `$ExecutionContext.SessionState.LanguageMode`.

### Anti-Patterns (Forbidden)

- Skipping `Invoke-Shakedown` after changes to `ValueFromPipeline`, parameter sets, or `trap`/`try`/`catch` handling.
- Expanding `Invoke-Shakedown` into a Pester-style suite with dozens of `Assert` calls.
- Running shakedown against mocked cmdlets via `Mock` — shakedown must exercise real providers.
- Running shakedown in `ConstrainedLanguage` mode when production runs in `FullLanguage` (or vice versa).
- Discarding the `Start-Transcript` output — an unrecorded shakedown did not happen.
- Writing shakedown scratch data under `$env:TEMP`, `[System.IO.Path]::GetTempPath()`, or any path containing `tmp`.

---
[Back to Overview](./OVERVIEW.md)
