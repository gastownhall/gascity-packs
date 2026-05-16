# module.xml Manifest

The build plugin generates `module.xml`. Do not hand-edit. The generated structure is:

| Element | Constraint |
|:--------|:-----------|
| `<id>` | Reverse-DNS module identifier (`com.company.modulename`); must remain stable across versions |
| `<version>` | Format: `major.minor.revision[-rcN][-betaN]`. The literal value `dev` bypasses version equality checks; ship only semantic versions |
| `<requiredignitionversion>` | Lowest 8.1.x version that supplies every SDK class referenced |
| `<requiredframeworkversion>` | Integer. 8.1 modules typically require framework version 7 or 8 |
| `<hook scope="G\|D\|C">FQN</hook>` | One hook per scope |
| `<jar scope="G\|D\|C\|CD\|GCD">jarname.jar</jar>` | Controls which scopes load the jar |
| `<export>jarname.jar</export>` | Gateway-only; promotes to higher classloader so dependent modules see the types. **Export changes require Gateway restart.** |
| `<depends scope="..." required="true\|false">moduleId</depends>` | Declared dependency on another module |
| `<license>` | HTML file at archive root; presented for end-user acceptance during install |
| `<documentation>` | Path to `doc/index.html`; mounted at `/main/system/docs/<module-id>/` |

---
[Back to Overview](./OVERVIEW.md)
