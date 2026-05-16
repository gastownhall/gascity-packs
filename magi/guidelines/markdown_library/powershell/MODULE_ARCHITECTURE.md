# Module Architecture

### Module Structure

```text
ModuleName/
├── ModuleName.psd1              # Module manifest
├── ModuleName.psm1              # Root module
├── Public/                      # Exported functions
│   ├── Get-Something.ps1
│   ├── Set-Something.ps1
│   └── New-Something.ps1
├── Private/                     # Internal functions
│   ├── Initialize-Module.ps1
│   └── Convert-InternalFormat.ps1
├── Classes/                     # PowerShell classes
│   └── ModuleClasses.ps1
├── en-US/                       # Localized help
│   └── about_ModuleName.help.txt
└── Tests/                       # Pester tests
    ├── Get-Something.Tests.ps1
    └── Module.Tests.ps1
```

### Module Manifest

```powershell
@{
    RootModule           = 'ModuleName.psm1'
    ModuleVersion        = '1.0.0'
    CompatiblePSEditions = @('Core', 'Desktop')
    GUID                 = 'xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx'
    Author               = 'Your Name'
    CompanyName          = 'Your Company'
    Copyright            = '(c) 2025 Your Company. All rights reserved.'
    Description          = 'Brief module description for gallery and Get-Module'
    PowerShellVersion    = '7.0'
    FunctionsToExport    = @('Get-Something', 'Set-Something', 'New-Something')
    CmdletsToExport      = @()
    VariablesToExport    = @()
    AliasesToExport      = @()
    PrivateData = @{
        PSData = @{
            Tags         = @('Tag1', 'Tag2')
            LicenseUri   = 'https://license.url'
            ProjectUri   = 'https://project.url'
            ReleaseNotes = 'Initial release'
        }
    }
}
```

### Root Module Pattern

```powershell
$Public  = @(Get-ChildItem -Path "$PSScriptRoot\Public\*.ps1" -ErrorAction SilentlyContinue)
$Private = @(Get-ChildItem -Path "$PSScriptRoot\Private\*.ps1" -ErrorAction SilentlyContinue)

foreach ($import in @($Public + $Private)) {
    try {
        . $import.FullName
    }
    catch {
        Write-Error "Failed to import function $($import.FullName): $_"
    }
}

Export-ModuleMember -Function $Public.BaseName
```

### Semantic Versioning

| Bump | Trigger |
|:-----|:--------|
| Major | Breaking changes to public API |
| Minor | New features, backward-compatible |
| Patch | Bug fixes, backward-compatible |

### Module Dependencies

```powershell
RequiredModules = @(
    @{ ModuleName = 'Az.Accounts';  ModuleVersion   = '2.0.0' }
    @{ ModuleName = 'Az.Resources'; RequiredVersion = '6.5.0' }
)
```

Use `ModuleVersion` for minimum version; `RequiredVersion` for exact pinning.

---
[Back to Overview](./OVERVIEW.md)
