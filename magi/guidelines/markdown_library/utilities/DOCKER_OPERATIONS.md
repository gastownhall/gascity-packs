# Docker Operations Module

### Container Lifecycle Management

| Script | Purpose |
|:-------|:--------|
| `build.sh` | Build container images with consistent tagging; build args, target stages, cache configuration |
| `run_local.sh` | Run containers locally with port mapping, volume mounts, environment injection |
| `start.sh` | Start stopped containers; single-container or all-containers modes; optional health-check wait |
| `stop.sh` | Stop running containers gracefully with timeout configuration and force-kill fallback |
| `deploy.sh` | Deploy images to remote hosts via SSH; image transfer, container replacement, health verification |
| `container_logs.sh` | Retrieve container logs with filtering options |

### Docker Helper Functions

| Function | Purpose |
|:---------|:--------|
| `docker_build` | Wraps `docker build` with logging and error handling |
| `docker_run` | Wraps `docker run` with port conflict detection and automatic cleanup |
| `docker_container_exists` | Checks if a container exists (running or stopped) |
| `docker_container_running` | Checks if a container is currently running |
| `docker_wait_healthy` | Polls container health status until healthy or timeout |
| `docker_port_free` | Checks if a host port is available for binding |
| `docker_kill_port` | Finds and kills containers using a specific port (use with caution) |

### Remote Docker Operations

- **SSH Credential Management** — Remote operations use `DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_PASS` from environment. The `ssh_helpers.sh` module provides `ensure_sshpass` for password-based authentication.
- **Image Transfer** — `deploy.sh` exports images locally, transfers via SCP, imports on the remote host. **Avoids registry dependencies for direct deployment.**
- **Remote Command Execution** — `ssh_run` executes Docker commands on remote hosts with proper error handling and output capture.

---
[Back to Overview](./OVERVIEW.md)
