# Redirect and Rewrite Patterns

### Prefer `return` Over `rewrite`

```nginx
# CORRECT — efficient and readable
return 301 https://example.com$request_uri;

# Use `rewrite` only when regex capture is required
rewrite ^/old/(.*)$ /new/$1 permanent;
```

`return` executes immediately without regex evaluation.

### Mark Terminal Rewrites

Use `last` (re-evaluates location) or `break` (stops rewrite processing). **Omitting the flag causes rewrite loops.**

### Avoid `if` in Location Blocks

The NGINX documentation explicitly warns that `if` is not a general-purpose conditional and causes unexpected behavior with `proxy_pass`, `try_files`, and other directives.

| Safe Use of `if` | Unsafe Use |
|:-----------------|:-----------|
| `return`, `rewrite`, `set` | Conditional `proxy_pass`, conditional `try_files` |

Use `map` for variable-based conditional logic when possible.

---
[Back to Overview](./OVERVIEW.md)
