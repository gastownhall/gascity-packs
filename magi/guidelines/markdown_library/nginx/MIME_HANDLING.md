# Content Security and MIME Handling

```nginx
include       /etc/nginx/mime.types;
default_type  application/octet-stream;
charset       utf-8;
charset_types text/xml text/plain text/css application/javascript application/json;
```

| Rule | Detail |
|:-----|:-------|
| `default_type application/octet-stream` | Forces download for unknown types |
| Forbidden | `default_type text/html` — unknown content types render as HTML, enabling XSS via uploaded files |
| Modern MIME additions | `application/wasm`, `font/woff2`, `application/manifest+json`, `image/avif` — add if missing from default |
| `charset utf-8` + `charset_types` | Prevents encoding-confusion XSS |

---
[Back to Overview](./OVERVIEW.md)
