# Project Structure and Organization

### Standard Directory Layout

```text
project/
├── pom.xml
├── src/
│   ├── main/
│   │   ├── java/
│   │   ├── resources/
│   │   └── webapp/        (web projects only)
│   ├── test/
│   │   ├── java/
│   │   └── resources/
│   └── it/                (integration tests)
├── target/                (generated)
└── README.md
```

### Coordinate Naming

- Group ID matches organization domain (reverse DNS notation).
- Artifact ID is lowercase with hyphens for multi-word names.
- Version follows semantic versioning (`MAJOR.MINOR.PATCH`).

```xml
<groupId>com.company.product</groupId>
<artifactId>service-name</artifactId>
<version>1.2.3</version>
```

### Multi-Module Structure

```text
parent-project/
├── pom.xml          (parent)
├── module-one/
│   └── pom.xml
├── module-two/
│   └── pom.xml
└── shared-resources/
    └── pom.xml
```

---
[Back to Overview](./OVERVIEW.md)
