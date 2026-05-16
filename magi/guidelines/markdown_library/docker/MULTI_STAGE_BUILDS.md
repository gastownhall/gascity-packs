# Multi-Stage Builds

### Purpose and Architecture

Multi-stage builds separate build-time dependencies from runtime artifacts. Each `FROM` instruction begins a new stage. Only the final stage becomes the output image; intermediate stages exist only during build. Build tools must never appear in the final stage.

### Standard Pattern

```dockerfile
FROM golang:1.22-alpine AS builder
WORKDIR /src
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -ldflags="-s -w" -o /app/server ./cmd/server

FROM gcr.io/distroless/static:nonroot
COPY --from=builder /app/server /server
USER nonroot:nonroot
ENTRYPOINT ["/server"]
```

### Stage Naming Conventions

- Name stages descriptively: `builder`, `deps`, `test`, `runtime`.
- Reference stages by name in `COPY --from=`: `COPY --from=builder /artifact /destination`.
- Unnamed stages are referenced by index (0, 1, 2); avoid this — names are clearer.

### Build Target Selection

Build specific stages with `--target`:
```bash
docker build --target builder -t myapp:builder .
docker build --target test -t myapp:test .
docker build -t myapp:latest .  # Builds final stage
```

Use targets for:
- CI pipelines that need intermediate artifacts
- Running tests in a container with test dependencies
- Creating debug images with additional tooling

### Dependency Caching Stage

For languages with separate dependency installation, create a dedicated dependency stage:

```dockerfile
FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --omit=dev

FROM node:20-alpine AS builder
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM node:20-alpine AS runtime
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY --from=builder /app/dist ./dist
USER node
CMD ["node", "dist/main.js"]
```

### Parallel Stages

Independent build stages run in parallel under BuildKit:

```dockerfile
FROM node:20-alpine AS frontend-builder
WORKDIR /app
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM golang:1.22-alpine AS backend-builder
WORKDIR /app
COPY backend/ ./
RUN go build -o server

FROM alpine:3.19 AS runtime
COPY --from=frontend-builder /app/dist /www
COPY --from=backend-builder /app/server /usr/local/bin/
```

### Cross-Compilation

Multi-stage builds enable cross-compilation with build arguments:

```dockerfile
FROM --platform=$BUILDPLATFORM golang:1.22-alpine AS builder
ARG TARGETPLATFORM TARGETOS TARGETARCH
WORKDIR /src
COPY . .
RUN GOOS=$TARGETOS GOARCH=$TARGETARCH go build -o /app/server

FROM alpine:3.19
COPY --from=builder /app/server /server
ENTRYPOINT ["/server"]
```

Build for multiple platforms:
```bash
docker buildx build --platform linux/amd64,linux/arm64 -t myapp:latest .
```

### Anti-Pattern: Fat Image

Including the SDK and source in the final image is forbidden:

```dockerfile
# WRONG: SDK in runtime image
FROM mcr.microsoft.com/dotnet/sdk:8.0
COPY . .
RUN dotnet build
CMD ["dotnet", "run"]
```

Correct:

```dockerfile
FROM mcr.microsoft.com/dotnet/sdk:8.0 AS build
COPY . .
RUN dotnet publish -c Release -o /app

FROM mcr.microsoft.com/dotnet/aspnet:8.0
COPY --from=build /app .
ENTRYPOINT ["dotnet", "MyApp.dll"]
```

---
[Back to Overview](./OVERVIEW.md)
