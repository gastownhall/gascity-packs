# Networking

### Network Modes

- **bridge**: Default; isolated network with NAT; suitable for most single-host deployments
- **host**: Container shares host network namespace; no isolation; use for performance-critical networking
- **none**: No networking; use for compute-only containers
- **container:name**: Share network namespace with another container; use for sidecar patterns
- **overlay**: Multi-host networking; encrypted on demand

Bridge networks in Compose:
```yaml
networks:
  frontend:
    driver: bridge
  backend:
    driver: bridge
    internal: true  # No external access
```

Encrypted overlay network:
```yaml
networks:
  app-net:
    driver: overlay
    attachable: true
    encrypted: true
```

### Port Exposure

`EXPOSE` in Dockerfile documents intended ports but does not publish them. Publish ports at runtime:

```bash
docker run -p 8080:8080 myimage           # Bind to all interfaces
docker run -p 127.0.0.1:8080:8080 myimage # Bind to localhost only
docker run -P myimage                      # Publish all EXPOSE'd ports to random host ports
```

### Service Discovery

Use DNS-based service discovery via container/service names. Hardcoded IP addresses are prohibited.

Correct:
```text
http://api-service:8080
```

Forbidden:
```text
http://172.17.0.5:8080
```

### Custom Networks

Create user-defined networks for multi-container applications:

```bash
docker network create --driver bridge app-network
docker run --network app-network --name api myimage
docker run --network app-network --name worker myimage
```

Containers on the same user-defined network resolve each other by container name. The default bridge network does not provide automatic DNS resolution.

### Network Isolation

Segment networks by trust boundary:

```yaml
services:
  web:
    networks: [frontend, backend]
  api:
    networks: [backend, data]
  database:
    networks: [data]  # Only accessible to API

networks:
  frontend:
  backend:
  data:
    internal: true
```

### Network Security

- Never expose database ports to the host; keep them internal to the Docker network.
- Use network aliases for service discovery within the network.
- Implement network policies in orchestration platforms to restrict container-to-container traffic.
- Prefer internal networks for backend services that don't need external access.

---
[Back to Overview](./OVERVIEW.md)
