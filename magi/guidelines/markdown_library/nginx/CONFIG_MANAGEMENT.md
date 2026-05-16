# Configuration Management and Testing

| Practice | Detail |
|:---------|:-------|
| Version control | All NGINX configuration files in Git; every change committed, reviewed, traceable |
| `nginx -t` in CI/CD | Validate syntax, missing files, invalid directives, certificate path errors. Gate deployment on test success |
| `nginx -T` (capital T) | Dump full resolved configuration including all includes; pipe to file for auditing — catches include ordering issues and directive override surprises |
| Graceful reload | `nginx -s reload`, not restart. Reload applies new configuration without dropping existing connections |
| Rollback procedure | Keep previous known-good configuration; automate rollback trigger; test rollback in staging |

---
[Back to Overview](./OVERVIEW.md)
