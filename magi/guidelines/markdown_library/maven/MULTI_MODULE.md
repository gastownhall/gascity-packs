# Multi-Module Projects

### Parent POM Structure

```xml
<project>
    <modelVersion>4.0.0</modelVersion>
    <groupId>com.company.product</groupId>
    <artifactId>parent</artifactId>
    <version>1.0.0</version>
    <packaging>pom</packaging>
    <modules>
        <module>common</module>
        <module>domain</module>
        <module>service</module>
        <module>web</module>
        <module>integration-tests</module>
    </modules>
    <properties>
        <!-- CI-friendly version management -->
        <revision>1.0.0</revision>
        <changelist>-SNAPSHOT</changelist>
        <sha1/>
    </properties>
    <dependencyManagement>
        <dependencies>
            <!-- Internal modules -->
            <dependency>
                <groupId>${project.groupId}</groupId>
                <artifactId>common</artifactId>
                <version>${project.version}</version>
            </dependency>
            <dependency>
                <groupId>${project.groupId}</groupId>
                <artifactId>domain</artifactId>
                <version>${project.version}</version>
            </dependency>
            <dependency>
                <groupId>${project.groupId}</groupId>
                <artifactId>service</artifactId>
                <version>${project.version}</version>
            </dependency>
        </dependencies>
    </dependencyManagement>
</project>
```

### Sibling Module References

Reference sibling modules without versions; the parent's `dependencyManagement` controls them:

```xml
<dependencies>
    <dependency>
        <groupId>${project.groupId}</groupId>
        <artifactId>common</artifactId>
    </dependency>
</dependencies>
```

### Reactor Build

```xml
<build>
    <plugins>
        <plugin>
            <groupId>org.apache.maven.plugins</groupId>
            <artifactId>maven-reactor-plugin</artifactId>
            <version>1.1</version>
            <configuration>
                <makeMode>incremental</makeMode>
                <resumeFrom>${resumeFrom}</resumeFrom>
            </configuration>
        </plugin>
    </plugins>
</build>
```

Maven automatically determines build order from inter-module dependencies. For explicit control, list modules in dependency order:

```xml
<modules>
    <module>common</module>     <!-- No dependencies -->
    <module>service</module>    <!-- Depends on common -->
    <module>web</module>        <!-- Depends on service -->
</modules>
```

---
[Back to Overview](./OVERVIEW.md)
