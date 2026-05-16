# Networking

### Service Types

| Type | Use |
|:-----|:----|
| **ClusterIP** | Internal-only; default for service-to-service |
| NodePort | Avoid for production — use Ingress instead |
| LoadBalancer | Non-HTTP services requiring external access |
| ExternalName | DNS alias to external service — use sparingly; creates tight coupling |

### Network Policies — Default Deny

Default deny with explicit allow is the secure pattern:

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-all
  namespace: payments
spec:
  podSelector: {}
  policyTypes:
  - Ingress
  - Egress
```

Explicit allow:

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-ingress
  namespace: payments
spec:
  podSelector:
    matchLabels:
      app: api
  policyTypes:
  - Ingress
  ingress:
  - from:
    - namespaceSelector:
        matchLabels:
          name: ingress-system
    - podSelector:
        matchLabels:
          app: nginx
    ports:
    - protocol: TCP
      port: 8080
```

Required allows per workload:

- Ingress from ingress controller namespace.
- Egress to required databases and external APIs.
- Pod-to-pod communication within namespace where needed.

NetworkPolicies require a CNI that enforces them. Azure CNI with network policy (Calico or Azure native) provides enforcement; verify policy enforcement is enabled before relying on policies for security.

### DNS Configuration

CoreDNS handles cluster DNS resolution. Standard service discovery: `<service>.<namespace>.svc.cluster.local`.

For external DNS resolution:

- Configure custom upstream resolvers for internal domains.
- Use ExternalDNS controller to synchronize ingress records with Azure DNS.
- Set appropriate TTLs; low TTLs increase DNS query load, high TTLs delay failover.

### Service Mesh

Service mesh (Istio, Linkerd) adds mTLS, observability, and traffic management at the cost of complexity and resource overhead.

**Adopt when:**

- mTLS between services is required (compliance, zero-trust).
- Advanced traffic management (canary, traffic splitting) exceeds ingress capabilities.
- Distributed tracing requires transparent instrumentation.

Istio strict-mTLS + canary routing example:

```yaml
apiVersion: security.istio.io/v1beta1
kind: PeerAuthentication
metadata:
  name: default
  namespace: payments
spec:
  mtls:
    mode: STRICT
---
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: api
spec:
  hosts:
  - api
  http:
  - match:
    - headers:
        canary:
          exact: "true"
    route:
    - destination:
        host: api
        subset: v2
      weight: 100
  - route:
    - destination:
        host: api
        subset: v1
      weight: 90
    - destination:
        host: api
        subset: v2
      weight: 10
```

**Linkerd** provides a lightweight alternative with automatic mTLS and lower resource overhead than Istio.

Avoid service mesh for simplicity when basic ingress, network policies, and application-level security suffice.

---
[Back to Overview](./OVERVIEW.md)
