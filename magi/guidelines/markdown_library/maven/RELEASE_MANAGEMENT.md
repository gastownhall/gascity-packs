# Release Management

### Maven Release Plugin

```xml
<plugin>
    <groupId>org.apache.maven.plugins</groupId>
    <artifactId>maven-release-plugin</artifactId>
    <version>3.0.1</version>
    <configuration>
        <autoVersionSubmodules>true</autoVersionSubmodules>
        <tagNameFormat>v@{project.version}</tagNameFormat>
        <releaseProfiles>release</releaseProfiles>
        <goals>deploy</goals>
        <pushChanges>false</pushChanges>
        <localCheckout>true</localCheckout>
        <preparationGoals>clean verify</preparationGoals>
        <completionGoals>generate-sources</completionGoals>
        <checkModificationExcludes>
            <checkModificationExclude>pom.xml</checkModificationExclude>
        </checkModificationExcludes>
    </configuration>
</plugin>
```

### Versions Maven Plugin (Updates)

```xml
<plugin>
    <groupId>org.codehaus.mojo</groupId>
    <artifactId>versions-maven-plugin</artifactId>
    <version>2.16.2</version>
    <configuration>
        <generateBackupPoms>false</generateBackupPoms>
        <rulesUri>file://${project.basedir}/maven-version-rules.xml</rulesUri>
    </configuration>
    <executions>
        <execution>
            <phase>compile</phase>
            <goals>
                <goal>display-dependency-updates</goal>
                <goal>display-plugin-updates</goal>
                <goal>display-property-updates</goal>
            </goals>
        </execution>
    </executions>
</plugin>
```

### CI-Friendly Versioning

```xml
<properties>
    <revision>1.0.0</revision>
    <changelist>-SNAPSHOT</changelist>
    <sha1/>
</properties>
<version>${revision}${changelist}${sha1}</version>
<!-- Override in CI/CD: -->
<!-- mvn clean deploy -Drevision=1.2.3 -Dchangelist= -Dsha1=.${BUILD_NUMBER} -->
```

---
[Back to Overview](./OVERVIEW.md)
