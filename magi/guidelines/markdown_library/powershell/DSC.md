# Desired State Configuration (DSC)

### Resource Module Structure

```text
MyDscResource/
├── MyDscResource.psd1
└── DSCResources/
    └── ResourceName/
        ├── ResourceName.psm1
        └── ResourceName.schema.mof
```

### Configuration with Data Separation

```powershell
Configuration WebServer {
    Import-DscResource -ModuleName PSDesiredStateConfiguration

    Node $AllNodes.NodeName {
        WindowsFeature IIS {
            Name   = 'Web-Server'
            Ensure = 'Present'
        }
    }
}
```

Package DSC resources as modules. Use configuration data separation to keep node identity and credentials out of configuration logic.

---
[Back to Overview](./OVERVIEW.md)
