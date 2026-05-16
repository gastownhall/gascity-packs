# Shakedown — Post-Deploy Validation

### Definition

A post-deploy shakedown is the **deliberate integration smoke sequence executed after `kubectl apply` or a Helm release converges**, validating that the workload actually functions as an integrated whole inside the target cluster.

It is **not**:

- A readiness probe — readiness gates a single Pod; shakedown gates the release.
- `kubectl apply --dry-run` or `helm lint` — those are preflight and do not execute the workload.
- Production load testing — shakedown uses known-good minimal traffic.

**Forbidden:** declaring a release successful solely on `kubectl rollout status` returning success.

### Mandatory Triggers

Shakedown runs after every rollout that changes:

- A Deployment, StatefulSet, DaemonSet, Job, CronJob, Service, Ingress, NetworkPolicy, HPA, PVC, ConfigMap binding, or ServiceAccount binding.
- First release of a new workload into a namespace.
- Helm chart major or minor upgrade.
- Container image change beyond a patch bump.
- Resource requests or limits.
- NetworkPolicy, Ingress, or Service surface change.
- Secret or ConfigMap schema change.
- PVC StorageClass or access mode change.
- ServiceAccount, Role, or RoleBinding change that affects the workload's cluster access.
- Cluster upgrade, node pool change, or CNI upgrade.

### Non-Triggers

- Image patch bumps that keep the Dockerfile runtime surface identical.
- HPA min/max adjustments inside a validated band.
- Label or annotation changes that do not affect selectors or policies.

### Validation Categories

1. **Rollout convergence** — `kubectl rollout status` converges within a bounded window for every workload object in the release.
2. **Pod readiness** — every Pod reaches Ready and stays Ready across a stability window. No `CrashLoopBackOff`, no `ImagePullBackOff`, no `OOMKilled`.
3. **Service DNS** — Service DNS resolves from a sibling namespace via the cluster DNS, returning the live endpoint slice.
4. **PVC mount** — PersistentVolumeClaim binds and is writable from inside the Pod with the expected UID/GID and `fsGroup`.
5. **Config injection** — ConfigMap and Secret values propagate to the expected environment variables and to the expected mount paths, with expected file permissions.
6. **Ingress TLS** — Ingress routes the expected host and path to the backing Service and serves a valid TLS chain.
7. **NetworkPolicy** — permits intended ingress and egress flows and denies unintended flows, verified by a test Pod in the cluster.
8. **HPA metrics** — the HPA's metrics source returns current values and the controller reports a computed replica count.
9. **ServiceAccount token** — projected token authenticates to the Kubernetes API with the expected RBAC scope for Pods that call the API.
10. **Probe endpoints** — liveness, readiness, and startup probe paths respond with the expected status codes from inside the Pod network.

### Execution Principles

- **Conservative traffic** — representative smoke requests, not load.
- **Progressive exercise** — start with cluster-internal probes, then add in-namespace calls, then cross-namespace DNS, then ingress TLS.
- **Controlled environment** — a dedicated namespace mirroring production labels, NetworkPolicies, and quotas.
- **Observable execution** — `kubectl logs`, `kubectl describe`, `kubectl get events -w`, and metrics snapshots captured for the shakedown window.
- **Known-good inputs** — pre-computed request bodies with known expected response shapes.
- **No HPA, probe, or resource tuning** during shakedown.

### Execution Pattern

| Step | Action |
|:----:|:-------|
| 1 | Confirm preflight: manifests lint cleanly, diff-against-live is expected, images are pullable, CRDs exist |
| 2 | Apply manifests or upgrade the Helm release into the target namespace |
| 3 | Run `kubectl rollout status` for every workload with a bounded `--timeout` |
| 4 | Assert all Pods are Ready and stable across the stability window |
| 5 | Launch an in-cluster shakedown Job that resolves Service DNS, calls probe endpoints, writes to any mounted PVC, and issues a representative request |
| 6 | Verify Ingress via `curl` against the external hostname with TLS verification enabled |
| 7 | Verify NetworkPolicy by issuing allowed and denied requests from a test Pod |
| 8 | Snapshot `kubectl get events`, `kubectl top pods`, and `kubectl describe` for all release objects |
| 9 | Record classification and store artifacts |

### Reference Shakedown Job

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: shakedown-release
  namespace: app-staging
  labels:
    app.kubernetes.io/component: shakedown
spec:
  backoffLimit: 0
  ttlSecondsAfterFinished: 3600
  template:
    spec:
      restartPolicy: Never
      serviceAccountName: shakedown-runner
      containers:
        - name: runner
          image: ghcr.io/org/shakedown:1.4.2
          env:
            - name: TARGET_SERVICE
              value: app.app-staging.svc.cluster.local
            - name: INGRESS_HOST
              value: app.staging.example.com
          command: ["/bin/sh","-c"]
          args:
            - |
              set -euo pipefail
              getent hosts "${TARGET_SERVICE}"
              curl -fsS "http://${TARGET_SERVICE}/healthz"
              curl -fsS "http://${TARGET_SERVICE}/readyz"
              curl -fsS --resolve "${INGRESS_HOST}:443:$(getent hosts ingress-nginx-controller.ingress-nginx.svc.cluster.local | awk '{print $1}')" "https://${INGRESS_HOST}/healthz"
              echo "shakedown: pass"
```

Driver script (project-local artifact directory `.shakedown/`):

```bash
kubectl rollout status deployment/app -n app-staging --timeout=180s
kubectl wait --for=condition=Ready pod -l app=app -n app-staging --timeout=180s
kubectl apply -f shakedown-job.yaml
kubectl wait --for=condition=complete job/shakedown-release -n app-staging --timeout=300s
kubectl logs job/shakedown-release -n app-staging > .shakedown/release.log
kubectl get events -n app-staging --sort-by=.lastTimestamp > .shakedown/events.log
```

### Result Classification

- **Pass** — rollout converges, all categories validate, no abnormal events in the shakedown window.
- **Fail-blocking** — rollout does not converge; Pods `CrashLoopBackOff` or `ImagePullBackOff`; Service DNS fails; PVC fails to mount; Ingress returns 5xx; NetworkPolicy blocks intended traffic or permits forbidden traffic; ServiceAccount token rejected by the API.
- **Fail-nonblocking** — stable Ready with benign warning events; HPA metrics source lag within retry budget; TLS chain valid but missing an intermediate.
- **Inconclusive** — cluster-level outage unrelated to the release; admission controller webhook timeout; noisy neighbor preventing observation.

### Required Artifacts

- **Rollout log** — output of `kubectl rollout status` for every workload object.
- **Events snapshot** — `kubectl get events --sort-by=.lastTimestamp` for the namespace across the window.
- **Describe bundle** — `kubectl describe` output for every release object.
- **Pod logs** — `kubectl logs` for every Pod including previous container logs on restart.
- **Cluster version** — `kubectl version`, node pool versions, CNI plugin version.
- **Image digests** — fully qualified image references with digests for every container.
- **Issue list** — every anomaly observed, classified blocking or non-blocking, with reproduction context.

### Anti-Patterns (Forbidden)

- Running shakedown against a Minikube or kind cluster when the target is a managed cloud cluster.
- Shakedown against stub Services that front no real backend.
- Skipping Ingress validation because the Service is reachable inside the namespace.
- Treating shakedown as a full end-to-end regression suite.
- Deleting the shakedown Job without persisting its logs and artifacts.

---
[Back to Overview](./OVERVIEW.md)
