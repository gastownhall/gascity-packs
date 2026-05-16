# Automation Templates

### Ansible Provisioning

```yaml
---
- name: Provision LXC Container
  hosts: proxmox-host
  tasks:
    - name: Create container
      proxmox:
        vmid: "{{ container_id }}"
        hostname: "{{ container_hostname }}"
        ostemplate: "local:vztmpl/{{ template_name }}"
        password: "{{ container_password }}"
        unprivileged: yes
        cores: "{{ cpu_cores }}"
        memory: "{{ memory_mb }}"
        swap: 0
        storage: "{{ storage_backend }}"
        disk: "{{ disk_gb }}"
        netif:
          net0: "name=eth0,bridge=vmbr0,ip={{ ip_address }}/24,gw={{ gateway }}"
        onboot: yes
        state: present
    - name: Start container
      proxmox:
        vmid: "{{ container_id }}"
        state: started
    - name: Wait for container
      wait_for:
        host: "{{ ip_address }}"
        port: 22
        delay: 10
```

### Bulk Operations

```bash
#!/bin/bash
# Bulk container operations
ACTION="${1:-status}"
NODE="${2:-$(hostname)}"
# Get all container IDs
CONTAINERS=$(pvesh get /nodes/$NODE/lxc --output-format json | jq -r '.[].vmid')
case "$ACTION" in
    start)
        for vmid in $CONTAINERS; do
            pct start $vmid
        done
        ;;
    stop)
        for vmid in $CONTAINERS; do
            pct shutdown $vmid
        done
        ;;
    backup)
        for vmid in $CONTAINERS; do
            vzdump $vmid --mode snapshot --compress zstd --storage backup-store
        done
        ;;
    status)
        for vmid in $CONTAINERS; do
            status=$(pct status $vmid | awk '{print $2}')
            echo "Container $vmid: $status"
        done
        ;;
esac
```

---
[Back to Overview](./OVERVIEW.md)
