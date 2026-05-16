# POM File Configuration

### POM Element Order

Maintain consistent ordering in every POM:

| Order | Element |
|:-----:|:--------|
| 1 | `modelVersion` and coordinates |
| 2 | `parent` declaration |
| 3 | Project information (`name`, `description`, `url`) |
| 4 | `properties` |
| 5 | `dependencyManagement` |
| 6 | `dependencies` |
| 7 | `build` configuration |
| 8 | `profiles` |
| 9 | `distributionManagement` |

### Minimal POM Template

```xml
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 http://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>
    <groupId>com.company.product</groupId>
    <artifactId>project-name</artifactId>
    <version>1.0.0</version>
    <packaging>jar</packaging>
    <name>Project Display Name</name>
    <description>Brief project description</description>
    <properties>
        <maven.compiler.source>21</maven.compiler.source>
        <maven.compiler.target>21</maven.compiler.target>
        <project.build.sourceEncoding>UTF-8</project.build.sourceEncoding>
        <project.reporting.outputEncoding>UTF-8</project.reporting.outputEncoding>
    </properties>
    <dependencyManagement>
        <!-- Dependency versions -->
    </dependencyManagement>
    <dependencies>
        <!-- Project dependencies -->
    </dependencies>
    <build>
        <!-- Build configuration -->
    </build>
</project>
```

---
[Back to Overview](./OVERVIEW.md)
