# FastCGI / PHP-FPM Integration

### Use Unix Sockets

```nginx
fastcgi_pass unix:/run/php/php-fpm.sock;
```

Unix sockets are faster (no TCP overhead) and securable with filesystem permissions. TCP (`127.0.0.1:9000`) only for cross-host communication.

### Path Traversal Mitigation

```nginx
location ~ \.php$ {
    try_files $uri =404;            # MUST be present — prevents path traversal exploit
    fastcgi_pass unix:/run/php/php-fpm.sock;
    fastcgi_index index.php;
    include fastcgi_params;
    fastcgi_param SCRIPT_FILENAME $document_root$fastcgi_script_name;
}
```

Set `cgi.fix_pathinfo=0` in `php.ini`. Without `try_files $uri =404` before `fastcgi_pass`, NGINX + PHP-FPM processes requests like `/uploads/image.jpg/malicious.php`, executing `malicious.php` if uploaded disguised as an image.

### PHP-FPM Hygiene

- Always include `fastcgi_params` (or `fastcgi.conf`).
- Set `SCRIPT_FILENAME` explicitly.

### Block PHP in Upload Directories

```nginx
location ~* /uploads/.*\.php$ {
    deny all;
    return 403;
}
```

Upload directories are the **primary vector for webshell deployment**. Uploaded `.php` files must never execute.

### FastCGI Caching

For cacheable PHP responses (marketing pages, product listings), configure `fastcgi_cache`. Cache key includes request method, scheme, host, URI. Set bypass and purge mechanisms for invalidation. **Reduces PHP-FPM load by 80–95%** for cacheable content.

---
[Back to Overview](./OVERVIEW.md)
