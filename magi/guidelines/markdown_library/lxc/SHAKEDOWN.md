# Shakedown — Post-Provision Validation

### Definition

An LXC post-provision shakedown is the **controlled validation sequence executed after `lxc launch`, `pct create`, or cloud-init convergence**, confirming that the container is not only RUNNING but has fully reached the declared operating state with functioning network, storage, services, and identity injection.

Shakedown is **not**:

- Static profile validation (`lxc profile show`) — does not execute the container.
- Application load testing — that runs after shakedown passes.

### Mandatory Triggers

Shakedown runs after every provisioning event that creates or recreates a container, or that alters its config profile, network, storage, or user-data:

- First provisioning of a new container.
- Template or image change.
- cloud-init `user-data` or `vendor-data` change.
- Profile or config key change affecting security, resources, or devices.
- Bind-mount or storage backend change.
- Network bridge, VLAN, or static IP change.
- Privileged/unprivileged conversion or UID/GID mapping change.
- LXD or Proxmox host upgrade that affects the container runtime.

### Non-Triggers

- Routine package updates inside a long-running container that pass the normal service health check.
- Log rotation or scheduled backup runs.
- Restart of the container without configuration changes.

### Validation Categories

1. **Runtime state** — container transitions to RUNNING within the declared provisioning budget and stays RUNNING across the stability window.
2. **cloud-init status** — `cloud-init status` reports `done` (not `error` or `disabled`); `/var/log/cloud-init.log` and `/var/log/cloud-init-output.log` contain no fatal entries.
3. **Network reachability** — container holds the expected IPv4/IPv6 address on the expected bridge, reaches its gateway, and resolves external DNS.
4. **Bind mounts** — every declared bind mount is present inside the container with expected content, ownership in the mapped UID/GID namespace, and expected mode.
5. **systemd services** — every systemd unit declared in user-data reaches `active (running)` and `journalctl` reports no repeated restart loops.
6. **Log writability** — declared log paths are writable by the service user; log rotation configuration is in place.
7. **DNS resolution** — `/etc/resolv.conf` resolves the expected upstream; queries for both internal and external records succeed.
8. **Package repositories** — package manager reaches configured repositories; refresh completes without 4xx or 5xx errors.
9. **SSH keys** — authorized SSH keys declared via cloud-init or the provisioning profile are present in the target user's `authorized_keys` with expected mode and ownership.
10. **Resource limits** — memory, CPU, and disk limits declared in the profile are visible inside the container through `/sys/fs/cgroup` and `systemd-cgtop`.

### Execution Principles

- **Conservative** — read-only probes via `lxc exec` and `pct exec`; no config mutation.
- **Progressive exercise** — container state first, then cloud-init, then network, then storage, then services, then resource limits.
- **Controlled environment** — a dedicated provisioning host or validation node mirroring the production Proxmox cluster configuration.
- **Observable execution** — capture `lxc info`, `pct config`, `journalctl`, and cloud-init logs for the shakedown window.
- **Known-good inputs** — expected IP, expected service list, expected mount paths, expected package sources committed to the provisioning repository.
- **No service tuning, kernel parameter tweaking, or template editing** during shakedown.

### Execution Pattern

| Step | Action |
|:----:|:-------|
| 1 | Confirm preflight: profile exists, template is present, storage pool has capacity, bridge is up |
| 2 | Provision the container via `lxc launch` or `pct create`; capture the container id |
| 3 | Wait for RUNNING state within the declared budget |
| 4 | Wait for `cloud-init status --wait` to return done |
| 5 | Verify network: `ip a`, `ip r`, `getent hosts`, `ping -c 2 gateway` |
| 6 | Verify mounts: `findmnt`; assert expected paths, ownership, and mode |
| 7 | Verify systemd: `systemctl is-system-running`, `is-active` for every declared unit |
| 8 | Verify package manager: `apt-get update` or `dnf makecache` with exit-code check |
| 9 | Verify SSH keys: `cat /home/user/.ssh/authorized_keys` with expected fingerprints |
| 10 | Verify resource limits: `cat /sys/fs/cgroup/memory.max` compared to profile declaration |
| 11 | Record classification and store artifacts keyed by container id and provisioning timestamp |

### Result Classification

- **Pass** — container is RUNNING, cloud-init is done, network and DNS reach expected targets, mounts are correct, all services are active, resource limits match profile.
- **Fail-blocking** — container stuck in STOPPED or STARTING past budget; cloud-init reports error; declared IP missing or gateway unreachable; bind-mount missing or unwritable; declared systemd unit in failed state; SSH keys absent; resource limits absent from cgroup.
- **Fail-nonblocking** — optional service not yet active inside its start grace window; package mirror slow but reachable; non-fatal cloud-init warning.
- **Inconclusive** — host-level outage; storage pool degraded; cluster quorum loss; upstream DNS outage preventing observation.

### Required Artifacts

- **Container info** — `lxc info <container>` or `pct config <vmid>` captured to file.
- **cloud-init log** — `/var/log/cloud-init.log` and `/var/log/cloud-init-output.log` copied from the container.
- **journalctl snapshot** — `journalctl -b` captured for the shakedown window.
- **Network state** — `ip a`, `ip r`, `getent hosts` output from inside the container.
- **Mount state** — `findmnt` output from inside the container.
- **Service state** — `systemctl list-units --state=failed` and `is-active` for each declared unit.
- **Host metadata** — Proxmox or LXD host version, kernel, storage pool state, bridge definition.
- **Issue list** — every anomaly observed, classified blocking or non-blocking, with reproduction context.

### Anti-Patterns (Forbidden)

- Skipping shakedown after a "small" profile edit that touched devices, networks, or security keys.
- Running shakedown on a container provisioned outside the declared profile.
- Mutating the container to make validation pass instead of fixing the provisioning source.
- Treating shakedown as a full service test suite.
- Discarding cloud-init logs and journal snapshots after the run.

### Reference Shakedown Script

```bash
#!/usr/bin/env bash
# Post-provision shakedown for an LXC container
set -euo pipefail
NAME="${1:?container name required}"
OUT_DIR=".shakedown/${NAME}-$(date +%Y%m%dT%H%M%S)"
mkdir -p "${OUT_DIR}"

# 1. State
for i in {1..30}; do
    state=$(lxc info "${NAME}" | awk '/^Status:/ {print $2}')
    [[ "${state}" == "Running" ]] && break
    sleep 2
done
[[ "${state}" == "Running" ]] || { echo "FAIL: container not running"; exit 1; }

# 2. cloud-init
lxc exec "${NAME}" -- cloud-init status --wait > "${OUT_DIR}/cloud-init.txt" \
    || { echo "FAIL: cloud-init did not reach done"; exit 1; }

# 3. Network
lxc exec "${NAME}" -- ip -4 a show dev eth0 > "${OUT_DIR}/ip.txt"
lxc exec "${NAME}" -- ip r > "${OUT_DIR}/routes.txt"
GW=$(lxc exec "${NAME}" -- sh -c "ip r | awk '/default/ {print \$3}'")
lxc exec "${NAME}" -- ping -c 2 -W 2 "${GW}" > "${OUT_DIR}/ping-gw.txt" \
    || { echo "FAIL: gateway unreachable"; exit 1; }
lxc exec "${NAME}" -- getent hosts example.com > "${OUT_DIR}/dns.txt" \
    || { echo "FAIL: DNS resolution failed"; exit 1; }

# 4. Mounts
lxc exec "${NAME}" -- findmnt --output TARGET,SOURCE,FSTYPE,OPTIONS > "${OUT_DIR}/mounts.txt"

# 5. Systemd
lxc exec "${NAME}" -- systemctl is-system-running > "${OUT_DIR}/systemd-state.txt" || true
lxc exec "${NAME}" -- systemctl list-units --state=failed --no-legend > "${OUT_DIR}/systemd-failed.txt"
[[ -s "${OUT_DIR}/systemd-failed.txt" ]] && { echo "FAIL: systemd units in failed state"; exit 1; }

# 6. Resource limits
lxc exec "${NAME}" -- sh -c 'cat /sys/fs/cgroup/memory.max || cat /sys/fs/cgroup/memory/memory.limit_in_bytes' \
    > "${OUT_DIR}/mem-limit.txt"

# 7. Persist host-side state
lxc info "${NAME}" > "${OUT_DIR}/lxc-info.txt"
lxc config show "${NAME}" > "${OUT_DIR}/lxc-config.yaml"
echo "PASS: shakedown ${NAME}"
```

---
[Back to Overview](./OVERVIEW.md)
