# Advanced Function Patterns

### Dynamic Parameters

```powershell
function Get-Data {
    [CmdletBinding()]
    param()

    DynamicParam {
        $paramDictionary = New-Object System.Management.Automation.RuntimeDefinedParameterDictionary
        if (Test-Path 'config.json') {
            $attribute = New-Object System.Management.Automation.ParameterAttribute
            $attribute.Mandatory = $true
            $attributeCollection = New-Object System.Collections.ObjectModel.Collection[System.Attribute]
            $attributeCollection.Add($attribute)
            $param = New-Object System.Management.Automation.RuntimeDefinedParameter('ConfigName', [string], $attributeCollection)
            $paramDictionary.Add('ConfigName', $param)
        }
        return $paramDictionary
    }
}
```

### Proxy Functions

```powershell
$metadata = New-Object System.Management.Automation.CommandMetadata (Get-Command Get-Process)
[System.Management.Automation.ProxyCommand]::Create($metadata)
```

### Argument Completers

```powershell
Register-ArgumentCompleter -CommandName Get-Service -ParameterName Name -ScriptBlock {
    param($commandName, $parameterName, $wordToComplete, $commandAst, $fakeBoundParameter)
    Get-Service -Name "$wordToComplete*" | ForEach-Object {
        [System.Management.Automation.CompletionResult]::new($_.Name, $_.Name, 'ParameterValue', $_.DisplayName)
    }
}
```

---
[Back to Overview](./OVERVIEW.md)
