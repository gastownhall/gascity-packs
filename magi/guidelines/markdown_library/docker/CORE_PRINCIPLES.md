# Core Principles

These guidelines define strict, reproducible, and secure patterns for all Docker-based containerization, optimizing for:

- **Immutability**: Containers are disposable artifacts built from deterministic specifications; runtime mutation of the container filesystem is prohibited except for tmpfs.
- **Minimal Attack Surface**: Every package, layer, and exposed port increases risk; include only what the application requires to function. No debugging tools in production images. No SSH servers in containers.
- **Reproducibility**: Builds produce identical images given identical inputs. Pin every dependency and base image. No network fetches during runtime. Use BuildKit reproducible builds.
- **Container as Deployment Unit**: A container image is a complete, self-contained deployment artifact. Include everything needed to run; never depend on host-level prerequisites.
- **Externalized Configuration**: Configuration lives outside the container — environment variables for runtime config, mounted secrets for sensitive data. Never bake environment-specific values into images.
- **Ephemeral Containers**: Containers can be stopped, started, or replaced at any moment. Maximum startup and shutdown time: 30 seconds. Never persist state in the container's local filesystem.
- **Layer Efficiency**: Each layer consumes storage and transfer bandwidth; optimize for cache utilization and minimal final image size.
- **Explicit Configuration**: No magic defaults, no implicit environment assumptions; every runtime behavior is declared in configuration.

### Primary Rule: Images Are Immutable Artifacts

A Docker image is a versioned, immutable artifact. Once built and tagged, it never changes. Configuration varies between environments through environment variables, mounted secrets, and orchestration configuration — never through runtime modification of the image or container filesystem. If you need different behavior, build a different image or change the runtime configuration.

### Secondary Rule: Smallest Possible Image

Every megabyte in an image increases pull time, storage cost, and attack surface. The ideal image contains the application binary, its runtime dependencies, and nothing else. No shells, no package managers, no debugging tools in production images. Debugging capabilities belong in sidecar containers or ephemeral debug sessions, not baked into the artifact.

### Build vs Runtime Separation

Build-time concerns (compilers, build tools, test frameworks, source code) never appear in runtime images. Multi-stage builds enforce this separation architecturally. The final stage contains only the executable artifact and its runtime dependencies. Build stages can be as bloated as necessary; final stages must be minimal.

---
[Back to Overview](./OVERVIEW.md)
