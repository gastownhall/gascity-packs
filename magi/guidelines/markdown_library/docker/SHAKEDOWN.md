# Container Shakedown

### Definition

A container shakedown is the **controlled end-to-end validation that a freshly built image actually operates inside a real container runtime**. It runs after every image build that changes the base image, entrypoint, installed packages, user, filesystem layout, exposed ports, or HEALTHCHECK.

A shakedown is distinct from:
- **Image build validation** (Hadolint, Trivy, SBOM scans) — these inspect the image without running it.
- **Production smoke tests** — these verify live traffic and external integrations.

A shakedown executes against the **built image tag**, not against dev-loop bind mounts. Skipping shakedown because the change "was minor" is forbidden when the change touched `ENTRYPOINT`, `USER`, `WORKDIR`, `VOLUME`, `EXPOSE`, or `HEALTHCHECK`.

### Mandatory Triggers

- First build of a new image.
- Base image upgrade or digest change.
- `ENTRYPOINT`, `CMD`, `USER`, or `WORKDIR` modification.
- `HEALTHCHECK` directive change.
- Addition or removal of a declared `VOLUME` mount point.
- Change to multi-stage build structure that alters the final layer.
- Switch between root and non-root execution.
- Introduction of read-only root filesystem.

### Non-Triggers

- Application source changes that do not touch the build graph or runtime surface.
- Dependency bumps fully covered by the existing HEALTHCHECK and startup path.
- Documentation, comments, or CI metadata changes inside the repository.

### Validation Categories

1. **Startup budget** — Container transitions from created to running within the declared startup budget; entrypoint reaches a steady state.
2. **HEALTHCHECK convergence** — HEALTHCHECK reports healthy within the declared timeout and the healthy state holds across consecutive intervals.
3. **Port listeners** — Every port declared by `EXPOSE` is actually `LISTEN`'ing inside the container and accepts a TCP handshake from the host and from a sibling container.
4. **Volume access** — Mounted volumes are readable and writable by the process user with the expected ownership and mode.
5. **Env propagation** — Environment variables supplied at run time are visible to PID 1 and to the application process tree.
6. **Secret readability** — Secret files are readable by the process user and never world-readable.
7. **Graceful shutdown** — Container responds to SIGTERM, flushes work, and exits within the declared stop timeout without falling through to SIGKILL.
8. **Log delivery** — Log output reaches the configured log driver with the expected format and without duplication.
9. **Non-root execution** — Entrypoint process runs as the declared non-root UID/GID, not as root.
10. **Read-only FS tolerance** — When the root filesystem is read-only, runtime write patterns resolve exclusively to declared tmpfs or named volume mounts.

### Execution Principles

- **Conservative inputs** — representative configuration, not adversarial or stress loads.
- **Progressive exercise** — start with plain `docker run`, then add volume mounts, then secrets, then network policy, then read-only root filesystem.
- **Controlled runtime** — use an isolated Docker context or dedicated shakedown network to prevent collision with live containers.
- **Observable runtime** — capture `docker logs`, `docker inspect`, and `docker events` for the full run window.
- **Known-good inputs** — inputs with pre-computed expected responses from the application.
- **No optimization during shakedown** — image size tuning, layer squashing, or startup tuning is forbidden during the run.

### Execution Pattern

| Step | Action |
|:----:|:-------|
| 1 | Confirm preflight: Hadolint clean, Trivy scan within policy, required build args supplied |
| 2 | Launch the container with representative env vars, volume mounts, and secrets in an isolated network |
| 3 | Wait for HEALTHCHECK to report healthy; assert declared startup budget is met |
| 4 | Probe every `EXPOSE` port from the host and from a sibling container on the same network |
| 5 | Exercise the simplest end-to-end path that writes through the expected volume and emits a log line |
| 6 | Verify logs arrive at the configured log driver and that secret paths remain non-world-readable |
| 7 | Issue `docker stop`; assert exit within the declared stop timeout with a clean exit code |
| 8 | Check for leaked resources: dangling volumes, orphaned networks, unreaped child processes |
| 9 | Record classification and store artifacts |

### Result Classification

- **pass** — Container starts, healthchecks converge, all categories validate, shutdown is graceful within budget.
- **fail-blocking** — Container exits non-zero on start, HEALTHCHECK never converges, declared port never listens, volume is unwritable, runs as root when non-root is required, or SIGTERM is ignored.
- **fail-nonblocking** — Startup exceeds soft budget but meets hard budget; log format drift that does not lose data; secret mode is correct but path location differs from convention.
- **inconclusive** — Host runtime version differs from target production runtime in a way that invalidates the observed behavior.

### Required Artifacts

- **Execution log** — full `docker logs` output with timestamps.
- **Inspect snapshot** — `docker inspect` of the container, its network, and its mounts.
- **Events trace** — `docker events` output for the shakedown window.
- **Image digest** — image digest, base image digest, Dockerfile SHA.
- **Runtime snapshot** — Docker Engine version, containerd version, runc version, host kernel.
- **Issue list** — every anomaly observed, classified blocking or non-blocking, with reproduction context.

### Anti-Patterns (Forbidden)

- Running shakedown against a dev bind-mount instead of the built image.
- Treating shakedown as a full test suite with dozens of assertions.
- Using docker-compose overrides that mask the production runtime configuration.
- Tuning image size or startup during the shakedown run.
- Discarding logs, events, or inspect output after the run completes.

### Reference Shakedown Script

```bash
#!/usr/bin/env bash
set -euo pipefail
IMAGE="myapp:${GIT_SHA}"
NET="shakedown-$$"
NAME="shakedown-${GIT_SHA}"
LOG_DIR=".shakedown/${GIT_SHA}"
mkdir -p "${LOG_DIR}"
docker network create --internal "${NET}"
trap 'docker rm -f "${NAME}" >/dev/null 2>&1 || true; docker network rm "${NET}" >/dev/null 2>&1 || true' EXIT
docker run -d --name "${NAME}" --network "${NET}" \
  --read-only --tmpfs /tmp:rw,size=64m \
  --user 10001:10001 \
  -e APP_ENV=shakedown \
  -v "$(pwd)/fixtures/data:/var/lib/app:rw" \
  --health-cmd='curl -fsS http://localhost:8080/healthz || exit 1' \
  --health-interval=2s --health-timeout=1s --health-retries=10 \
  "${IMAGE}"
for i in {1..30}; do
  status=$(docker inspect --format='{{.State.Health.Status}}' "${NAME}")
  [[ "${status}" == "healthy" ]] && break
  sleep 1
done
[[ "${status}" == "healthy" ]] || { echo "FAIL: healthcheck never converged"; exit 1; }
docker exec "${NAME}" id -u | grep -qx 10001 || { echo "FAIL: not running as non-root"; exit 1; }
docker exec "${NAME}" sh -c 'echo ok > /var/lib/app/shakedown.marker' || { echo "FAIL: volume not writable"; exit 1; }
docker logs "${NAME}" > "${LOG_DIR}/stdout.log" 2>&1
docker inspect "${NAME}" > "${LOG_DIR}/inspect.json"
start=$(date +%s)
docker stop --time=30 "${NAME}"
end=$(date +%s)
(( end - start <= 30 )) || { echo "FAIL: stop exceeded 30s"; exit 1; }
exit_code=$(docker inspect --format='{{.State.ExitCode}}' "${NAME}")
[[ "${exit_code}" == "0" || "${exit_code}" == "143" ]] || { echo "FAIL: dirty exit ${exit_code}"; exit 1; }
echo "PASS: shakedown for ${IMAGE}"
```

---
[Back to Overview](./OVERVIEW.md)
