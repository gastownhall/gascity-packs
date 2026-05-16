# Core Principles

This guide defines the principles, methodology, and complete instructions for containerizing existing applications. The focus is not on Docker mechanics or Kubernetes orchestration—those are covered elsewhere—but on the architectural thinking, decision frameworks, and implementation patterns that produce production-ready containerized applications.

- **Immutability First**: Containers are immutable deployment artifacts; configuration changes at runtime, not container contents
- **Explicit Dependencies**: Every dependency must be declared; implicit host-level dependencies break containerization
- **Environment Parity**: Development, staging, and production run identical container images; only configuration differs
- **Isolation by Design**: Each container has a single responsibility; monoliths decompose into cohesive, loosely-coupled services
- **Operational Readiness**: Containers must be observable, configurable, and capable of graceful lifecycle management

### Primary Rule: The Container Is the Deployment Unit

The container image is the complete, self-contained deployment artifact. It includes everything needed to run: application code, runtime, libraries, and dependencies. Nothing is assumed about the host except a container runtime.

This means:
- No "install these packages first" prerequisites
- No "copy these files to the server" steps
- No "ensure this environment variable is set on the host" requirements
- The image works identically on a developer laptop and in production

If you find yourself writing deployment documentation beyond "run this image with these environment variables," your containerization is incomplete.

### Secondary Rule: Configuration Lives Outside the Container

The container image is immutable. The same image runs in development, staging, and production. What changes between environments:
- Environment variables for runtime configuration
- Mounted secrets for sensitive data
- Volume mounts for persistent state (when applicable)
- Network configuration for service discovery

Hardcoding environment-specific values in images defeats the purpose of containerization. Every configuration value that differs between environments must be injectable at runtime.

### Tertiary Rule: Containers Are Ephemeral

Containers can be stopped, started, moved, or replaced at any moment. Applications must:
- Start quickly (seconds, not minutes)
- Shut down gracefully when signaled
- Not rely on local filesystem state surviving restarts
- Handle being killed without warning
- Recover cleanly when restarted

If your application requires careful startup sequences, manual initialization, or assumes it runs indefinitely on the same host, it is not container-ready.

---
[Back to Overview](./OVERVIEW.md)
