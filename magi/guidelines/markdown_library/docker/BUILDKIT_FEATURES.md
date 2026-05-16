# BuildKit Features

### Enable BuildKit Syntax

Pin the Dockerfile syntax frontend:

```dockerfile
# syntax=docker/dockerfile:1.5
```

### Cache Mounts

Cache mounts persist across builds without bloating layers.

apt cache:
```dockerfile
RUN --mount=type=cache,target=/var/cache/apt \
    --mount=type=cache,target=/var/lib/apt \
    apt-get update && apt-get install -y build-essential
```

pip cache:
```dockerfile
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-compile -r requirements.txt
```

Go cache:
```dockerfile
RUN --mount=type=cache,target=/go/pkg/mod \
    --mount=type=cache,target=/root/.cache/go-build \
    go build -o /app/server
```

### Heredoc Support

```dockerfile
RUN <<EOF
apt-get update
apt-get install -y curl
rm -rf /var/lib/apt/lists/*
EOF
```

### COPY --link

Independent layer reuse for unchanged copies:

```dockerfile
COPY --link /app/static /www/static
```

### Bind Mounts

Mount source-tree paths read-only into the build:

```dockerfile
RUN --mount=type=bind,source=.,target=/src \
    cd /src && make install
```

### SSH Mounts

Forward SSH agent for private repository access without leaking keys into layers:

```dockerfile
RUN --mount=type=ssh \
    git clone git@github.com:myorg/private-repo.git
```

---
[Back to Overview](./OVERVIEW.md)
