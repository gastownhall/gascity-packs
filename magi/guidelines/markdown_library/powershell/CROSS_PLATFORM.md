# Cross-Platform Considerations

### Platform Detection

```powershell
if ($IsWindows) {
    # Windows-specific code
}
elseif ($IsLinux) {
    # Linux-specific code
}
elseif ($IsMacOS) {
    # macOS-specific code
}
```

These automatic variables exist only in PowerShell 6+. For 5.1 compatibility:

```powershell
$isWindowsOS = $PSVersionTable.PSEdition -eq 'Desktop' -or $IsWindows
```

### Path Handling

```powershell
$configPath = [System.IO.Path]::Combine($HOME, '.config', 'myapp', 'config.json')
$tempFile   = [System.IO.Path]::GetTempFileName()
$logPath    = Join-Path -Path $PSScriptRoot -ChildPath 'logs' -AdditionalChildPath 'app.log'
```

### Line Endings

```powershell
$content = "Line 1$([Environment]::NewLine)Line 2"

# Or explicit control
$unixEndings = $content -replace "`r`n", "`n"
```

### Environment Variables

```powershell
$home = [Environment]::GetFolderPath('UserProfile')
$temp = [System.IO.Path]::GetTempPath()
```

Windows-specific variables (`$env:APPDATA`, `$env:LOCALAPPDATA`) don't exist on Linux/macOS.

### File System Case Sensitivity

Linux and macOS have case-sensitive file systems by default. Windows does not.

```powershell
# Works on Windows; may fail on Linux
$file = Get-Item 'Config.JSON'  # If actual file is 'config.json'
```

Use consistent casing. Test on target platforms.

---
[Back to Overview](./OVERVIEW.md)
