# Testing Strategy

### Pester Framework

```powershell
#Requires -Modules @{ ModuleName = 'Pester'; ModuleVersion = '5.0.0' }

Describe 'Get-ServiceStatus' {
    BeforeAll {
        Import-Module "$PSScriptRoot/../ModuleName.psd1" -Force
    }
    Context 'When service exists' {
        It 'Returns service information' {
            $result = Get-ServiceStatus -Name 'W32Time'
            $result | Should -Not -BeNullOrEmpty
            $result.Name | Should -Be 'W32Time'
        }
        It 'Accepts pipeline input' {
            $result = 'W32Time' | Get-ServiceStatus
            $result | Should -Not -BeNullOrEmpty
        }
    }
    Context 'When service does not exist' {
        It 'Throws an error' {
            { Get-ServiceStatus -Name 'NonExistentService123' } | Should -Throw
        }
    }
}
```

### Test Organization

```text
Tests/
├── Unit/
│   ├── Get-Something.Tests.ps1
│   └── Set-Something.Tests.ps1
├── Integration/
│   └── ModuleIntegration.Tests.ps1
└── Module.Tests.ps1
```

### Mocking

```powershell
Describe 'Get-ServerHealth' {
    BeforeAll {
        Mock Test-Connection { return $true }
        Mock Get-CimInstance { return @{ FreePhysicalMemory = 1000000 } }
    }
    It 'Returns healthy status when server responds' {
        $result = Get-ServerHealth -ComputerName 'Server01'
        $result.Status | Should -Be 'Healthy'
        Should -Invoke Test-Connection -Times 1 -Exactly
    }
}
```

### Code Coverage

```powershell
$config = New-PesterConfiguration
$config.Run.Path                = './Tests'
$config.CodeCoverage.Enabled    = $true
$config.CodeCoverage.Path       = './Public/*.ps1', './Private/*.ps1'
$config.CodeCoverage.OutputPath = './coverage.xml'
$config.CodeCoverage.OutputFormat = 'JaCoCo'
Invoke-Pester -Configuration $config
```

**Target 80%+ code coverage** for production modules.

---
[Back to Overview](./OVERVIEW.md)
