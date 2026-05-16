# Module Signing

### Development Mode

```properties
# ignition.conf — DEVELOPMENT GATEWAYS ONLY
wrapper.java.additional.N=-Dignition.allowunsignedmodules=true
```

**Never set this on a production Gateway.**

### module-signer.jar

```bash
java -jar module-signer.jar \
    -keystore=/path/to/keystore.jks \
    -keystore-pwd=KEYSTORE_PASSWORD \
    -alias=signing-alias \
    -alias-pwd=ALIAS_PASSWORD \
    -chain=cert.p7b \
    -module-in=in.modl \
    -module-out=signed.modl
```

The PKCS7 (`.p7b`) certificate chain must contain leaf → intermediates → root in order. Broken chains fail verification on install.

### Gradle Plugin Signing

```kotlin
// In build.gradle.kts (or convention plugin)
import io.ia.sdk.gradle.modl.task.SignModule

tasks.named<SignModule>("signModule") {
    // Configuration via gradle.properties keys (or env vars):
    //   ignition.signing.certAlias
    //   ignition.signing.certFile
    //   ignition.signing.keystoreFile
    //   ignition.signing.keystorePassword
}
```

**HSM signing:** PKCS#11 / YubiKey supported via `providerName` + `providerConfigPath`. See `SIGNING_VIA_HSM.md` in the plugin repo. Maven plugin does **not** support PKCS#11 — use Gradle for HSM.

---
[Back to Overview](./OVERVIEW.md)
