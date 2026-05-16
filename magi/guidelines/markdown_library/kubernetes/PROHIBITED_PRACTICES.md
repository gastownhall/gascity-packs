# Prohibited Practices

### Never Do

- Deploy pods without resource requests and limits — uncontrolled resource consumption destabilizes clusters.
- Use `latest` tag in production — image references must be immutable.
- Run containers as root without documented security review and compensating controls.
- Store secrets in ConfigMaps or environment variables visible in pod specs.
- Apply manifests imperatively without version control — configuration drift is guaranteed.
- Grant `cluster-admin` to developers or service accounts unless absolutely required.
- Deploy workloads without health probes — Kubernetes cannot manage unhealthy pods correctly.
- Ignore Pod Security Standards — default permissive configuration exposes unnecessary attack surface.
- Skip NetworkPolicies — flat network allows lateral movement after compromise.
- Use NodePort or hostPort for production services — use Ingress or LoadBalancer appropriately.
- Deploy single-replica production workloads — single points of failure violate availability requirements.
- Allow unlimited egress — pods should access only required external endpoints.
- Disable RBAC or use permissive bindings to "make things work".
- Store kubeconfig files with embedded credentials in repositories or shared locations.
- Mount service account tokens into pods that don't require Kubernetes API access.
- Declare a release successful solely on `kubectl rollout status` returning success without §18 shakedown.

---
[Back to Overview](./OVERVIEW.md)
