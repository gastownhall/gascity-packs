# Build Systems

### Gradle io.ia.sdk.modl Plugin (preferred)

```kotlin
// build.gradle.kts
plugins {
    id("io.ia.sdk.modl") version "0.4.x"
}

ignitionModule {
    name.set("My Module")
    fileName.set("My-Module.modl")
    id.set("com.company.modulename")
    moduleVersion.set("${project.version}")
    moduleDescription.set("Adds widget capabilities")
    requiredIgnitionVersion.set("8.1.0")

    projectScopes.putAll(mapOf(
        ":common"   to "GCD",
        ":gateway"  to "G",
        ":designer" to "D",
        ":client"   to "C"
    ))

    hooks.putAll(mapOf(
        "com.company.modulename.gateway.GatewayHook"   to "G",
        "com.company.modulename.designer.DesignerHook" to "D"
    ))

    moduleDependencies.putAll(mapOf(
        "com.inductiveautomation.vision" to "CD"
    ))
}

repositories {
    maven { url = uri("https://nexus.inductiveautomation.com/repository/public") }
    mavenCentral()
}

dependencies {
    compileOnly(libs.ignition.common.api)         // SDK artifacts: compileOnly only
    modlImplementation(libs.bundled.thirdParty)   // bundled jars in the .modl
    api(project(":common"))                       // inter-subproject
}
```

| Task | Purpose |
|:-----|:--------|
| `collectModlDependencies` | Resolve and stage runtime jars |
| `assembleModlStructure` | Lay out the module archive |
| `writeModuleXml` | Generate `module.xml` from DSL config |
| `zipModule` | Produce the unsigned `.modl` |
| `signModule` | Sign the `.modl` via configured keystore or HSM |
| `checksumModl` | Emit checksum file alongside the signed `.modl` |
| `deployModl` | Upload to a development Gateway running with `-Dia.developer.moduleupload=true` |
| `moduleAssemblyReport` | Diagnostic report on module composition |

### Maven ignition-maven-plugin

```xml
<plugin>
  <groupId>com.inductiveautomation.ignitionsdk</groupId>
  <artifactId>ignition-maven-plugin</artifactId>
  <version>1.0.x</version>
  <configuration>
    <projectScopes>
      <projectScope><name>common</name><scope>GCD</scope></projectScope>
      <projectScope><name>gateway</name><scope>G</scope></projectScope>
    </projectScopes>
    <moduleId>com.company.modulename</moduleId>
    <moduleName>My Module</moduleName>
    <moduleVersion>${project.version}</moduleVersion>
    <requiredIgnitionVersion>8.1.0</requiredIgnitionVersion>
    <requiredFrameworkVersion>8</requiredFrameworkVersion>
    <hooks>
      <hook><scope>G</scope><hookClass>com.company.modulename.gateway.GatewayHook</hookClass></hook>
    </hooks>
  </configuration>
</plugin>
```

| Goal | Purpose |
|:-----|:--------|
| `modl` | Package the `.modl` |
| `post` | Upload to development Gateway |

**Maven plugin limitation:** No PKCS#11 / HSM signing support — use Gradle for HSM.

---
[Back to Overview](./OVERVIEW.md)
