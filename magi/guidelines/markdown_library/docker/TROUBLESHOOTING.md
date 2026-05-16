# Troubleshooting

### Debug Commands

| Purpose | Command |
|:--------|:--------|
| View logs | `docker logs -f container_name` |
| Execute shell | `docker exec -it container_name /bin/sh` |
| View processes | `docker exec container_name ps aux` |
| Resource usage | `docker stats container_name` |
| Inspect config | `docker inspect container_name` |
| Export filesystem | `docker export container_name > container.tar` |

### Container Exit Codes

| Code | Meaning |
|:----:|:--------|
| 0 | Success |
| 1 | General error |
| 125 | Docker daemon error |
| 126 | Container command not executable |
| 127 | Container command not found |
| 137 | SIGKILL (often OOMKilled) |
| 139 | Segmentation fault |
| 143 | SIGTERM (graceful shutdown) |

Exit code 137 paired with `OOMKilled: true` in `docker inspect` indicates the container exceeded its memory limit. Exit code 143 indicates the container received and honored SIGTERM.

---
[Back to Overview](./OVERVIEW.md)
