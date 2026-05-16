# PSScriptAnalyzer

### Compliance

```powershell
Invoke-ScriptAnalyzer -Path . -Recurse -Settings PSGallery -Severity Error, Warning
```

**All scripts must pass PSScriptAnalyzer with no violations.**

### Custom Rules

```powershell
@{
    Rules = @{
        PSUseApprovedVerbs = @{
            Enable = $true
        }
        PSAvoidUsingWriteHost = @{
            Enable = $true
        }
        PSUseSingularNouns = @{
            Enable = $true
        }
    }
}
```

Define custom rules for organization standards.

---
[Back to Overview](./OVERVIEW.md)
