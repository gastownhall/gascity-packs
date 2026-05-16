# Build Context and Ignore Patterns

### Build Context Fundamentals

The build context is the set of files sent to the Docker daemon for build. A large context slows builds and risks including sensitive files. The context root is the path argument to `docker build`.

### .dockerignore Configuration

Create `.dockerignore` at the context root. Patterns follow `.gitignore` syntax:

```dockerignore
# Version control
**/.git
**/.gitignore
**/.gitattributes

# Dependencies (reinstalled in build)
**/node_modules
**/vendor
**/__pycache__
**/*.pyc
**/.venv
**/venv

# Build outputs
**/dist
**/build
**/target
**/bin
**/obj

# IDE and editor
**/.idea
**/.vscode
**/*.swp
**/*.swo
**/.DS_Store

# Docker artifacts
**/Dockerfile*
**/.dockerignore
**/docker-compose*.yml
**/.docker

# Documentation
**/*.md
**/docs
**/LICENSE

# Testing
**/coverage
**/.nyc_output
**/htmlcov
**/.pytest_cache
**/.tox

# Secrets (NEVER include)
**/.env
**/.env.*
**/*.pem
**/*.key
**/secrets
**/credentials

# CI/CD
**/.github
**/.gitlab-ci.yml
**/Jenkinsfile
**/azure-pipelines.yml
```

### Required `.dockerignore` Entries

At a minimum, `.dockerignore` MUST exclude `.git`, `node_modules`, `*.pyc`, `.env`, `Dockerfile*`, and `docker-compose*.yml`.

### Context Minimization Strategies

- Place Dockerfile at repository root to use the entire repo as context.
- Alternatively, place Dockerfile in a subdirectory and build with specific context path.
- Use `COPY` with specific paths rather than `COPY . .` to include only needed files.
- For monorepos, build from repo root but copy only the relevant service directory.

### Secret Handling in Build Context

Never include secrets in build context. Use BuildKit secret mounts (Section 10).

---
[Back to Overview](./OVERVIEW.md)
