# Security Scanning and Supply Chain

### Vulnerability Scanning

Integrate image scanning into CI; block on critical vulnerabilities and on high vulnerabilities in production.

Trivy:
```bash
trivy image --severity CRITICAL,HIGH --exit-code 1 myimage:latest
```

Snyk:
```bash
snyk container test myimage:latest --severity-threshold=high
```

Grype:
```bash
grype myimage:latest
```

Docker Scout:
```bash
docker scout cves myimage:latest
```

Build-time scanning stage:
```dockerfile
FROM aquasec/trivy:latest AS scanner
COPY --from=runtime /app /app
RUN trivy filesystem --exit-code 1 --severity HIGH,CRITICAL /app
```

### Software Bill of Materials (SBOM)

Generate SBOMs for supply-chain transparency:

```bash
docker sbom myimage:latest
syft myimage:latest -o spdx-json > sbom.json
```

### Image Signing

Sign images with cosign for supply-chain verification:

```bash
cosign sign --key cosign.key myregistry.io/myimage:latest
cosign verify --key cosign.pub myregistry.io/myimage:latest
```

---
[Back to Overview](./OVERVIEW.md)
