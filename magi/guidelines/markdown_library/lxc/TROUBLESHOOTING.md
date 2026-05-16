# Troubleshooting Patterns

### Startup Failure

**Symptoms:** Container fails to start, no console output.

**Diagnosis:**

```bash
pct start 101 --debug
journalctl -u pve-container@101
lxc-start -n 101 -F -l DEBUG -o /tmp/lxc-101.log
```

**Common causes:** storage not available; network bridge missing; resource limits preventing start; AppArmor denial.

### Permission Denied (Unprivileged)

**Symptoms:** Operations fail with permission errors in unprivileged containers.

**Diagnosis:**

```bash
ls -lan /path/on/host
stat -c "%u:%g" /path/in/container
```

**Solution:**

```bash
# Fix ownership for default mapping
chown -R 100000:100000 /host/path
# Or use ACLs for mixed access
setfacl -R -m u:100000:rwx /host/path
```

### Network Unreachable

**Symptoms:** Container cannot reach network.

**Diagnosis:**

```bash
ip a
ip r
cat /etc/resolv.conf
```

**Common causes:** missing or incorrect gateway; VLAN tag mismatch; firewall blocking traffic; bridge not connected to physical interface.

---
[Back to Overview](./OVERVIEW.md)
