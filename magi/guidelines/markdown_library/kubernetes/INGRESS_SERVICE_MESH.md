# Ingress and Service Mesh

### Ingress Controller Selection

| Controller | Notes |
|:-----------|:------|
| **NGINX Ingress Controller** | Standard choice; extensive documentation, wide adoption, AKS add-on available |
| **Azure Application Gateway Ingress (AGIC)** | Native Azure integration; WAF capability; suitable for Azure PaaS integration priority |
| **Traefik** | Modern feature set; native Kubernetes CRD support |

Choose **one** ingress controller type per cluster; multiple controllers create operational complexity.

### Ingress Configuration

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: api-ingress
  annotations:
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
    nginx.ingress.kubernetes.io/proxy-body-size: "10m"
spec:
  ingressClassName: nginx
  tls:
  - hosts:
    - api.example.com
    secretName: api-tls
  rules:
  - host: api.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: api-service
            port:
              number: 80
```

### TLS Certificate Management

Use cert-manager for automated certificate provisioning and renewal:

```yaml
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: api-tls
  namespace: payments
spec:
  secretName: api-tls
  issuerRef:
    name: letsencrypt-prod
    kind: ClusterIssuer
  dnsNames:
  - api.example.com
```

| Issuer | Use For |
|:-------|:--------|
| Let's Encrypt | Public endpoints |
| Internal CA | Cluster-internal services |
| Azure Key Vault | Certificates managed externally |

**Never deploy ingress without TLS in production. HTTP-to-HTTPS redirect is mandatory.**

### Rate Limiting and WAF

Configure rate limiting at ingress to protect against abuse:

- Global rate limits prevent cluster resource exhaustion.
- Per-client limits prevent individual bad actors from impacting others.

Enable WAF (via Application Gateway or ingress controller annotations) for public-facing services to block common attack patterns.

---
[Back to Overview](./OVERVIEW.md)
