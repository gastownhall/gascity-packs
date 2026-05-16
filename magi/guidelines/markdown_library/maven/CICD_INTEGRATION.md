# CI/CD Integration

### GitHub Actions

```yaml
# .github/workflows/maven.yml
name: Java CI with Maven
on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]
jobs:
  build:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        java: [ '21' ]
    steps:
    - uses: actions/checkout@v4
    - name: Set up JDK ${{ matrix.java }}
      uses: actions/setup-java@v4
      with:
        java-version: ${{ matrix.java }}
        distribution: 'temurin'
        cache: maven
    - name: Build with Maven
      run: mvn -B clean verify --file pom.xml
    - name: Generate coverage report
      run: mvn jacoco:report
    - name: Upload coverage to Codecov
      uses: codecov/codecov-action@v3
```

### Jenkins Pipeline

```groovy
pipeline {
    agent any
    tools {
        maven 'Maven-3.9.5'
        jdk 'JDK-21'
    }
    stages {
        stage('Build') {
            steps {
                sh 'mvn clean compile'
            }
        }
        stage('Test') {
            steps {
                sh 'mvn test'
            }
            post {
                always {
                    junit '**/target/surefire-reports/*.xml'
                }
            }
        }
        stage('Package') {
            steps {
                sh 'mvn package -DskipTests'
            }
        }
        stage('Deploy') {
            when {
                branch 'main'
            }
            steps {
                sh 'mvn deploy -DskipTests'
            }
        }
    }
}
```

### GitLab CI

```yaml
# .gitlab-ci.yml
image: maven:3.9.5-eclipse-temurin-21
variables:
  MAVEN_OPTS: "-Dmaven.repo.local=$CI_PROJECT_DIR/.m2/repository"
  MAVEN_CLI_OPTS: "--batch-mode --errors --fail-at-end --show-version"
cache:
  paths:
    - .m2/repository/
stages:
  - build
  - test
  - package
  - deploy
build:
  stage: build
  script:
    - mvn $MAVEN_CLI_OPTS compile
test:
  stage: test
  script:
    - mvn $MAVEN_CLI_OPTS test
  artifacts:
    reports:
      junit:
        - target/surefire-reports/TEST-*.xml
package:
  stage: package
  script:
    - mvn $MAVEN_CLI_OPTS package -DskipTests
  artifacts:
    paths:
      - target/*.jar
deploy:
  stage: deploy
  script:
    - mvn $MAVEN_CLI_OPTS deploy -DskipTests
  only:
    - main
```

---
[Back to Overview](./OVERVIEW.md)
