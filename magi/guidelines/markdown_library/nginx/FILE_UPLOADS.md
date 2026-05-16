# File Upload Handling

```nginx
location = /api/upload {
    client_max_body_size  100m;
    client_body_buffer_size 1m;
    proxy_read_timeout    300s;
    proxy_send_timeout    300s;
    proxy_pass            http://upload_upstream;
}
```

| Directive | Rule |
|:----------|:-----|
| `client_max_body_size` | Set per upload location; never `0` (unlimited) globally |
| `client_body_temp_path` | Partition with sufficient space; large uploads buffer here. Monitor disk usage |
| `proxy_read_timeout` / `proxy_send_timeout` | Increased per location for upload endpoints — a 100MB upload on a slow connection takes minutes |

---
[Back to Overview](./OVERVIEW.md)
