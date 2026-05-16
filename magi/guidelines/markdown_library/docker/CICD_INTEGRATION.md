# CI/CD Integration

### Automated Builds

- Build on every commit.
- Tag with Git SHA.
- Scan before push.

GitHub Actions example:
```yaml
- name: Build and push
  uses: docker/build-push-action@v5
  with:
    context: .
    push: true
    tags: |
      ${{ env.REGISTRY }}/${{ env.IMAGE }}:${{ github.sha }}
      ${{ env.REGISTRY }}/${{ env.IMAGE }}:latest
    cache-from: type=gha
    cache-to: type=gha,mode=max
```

### Tagging Strategy

For each released image, push the following tags:

| Tag | Example |
|:----|:--------|
| Semantic | `1.2.3` |
| Minor | `1.2` |
| Major | `1` |
| Git SHA | `sha-abc123` |
| Branch + SHA | `main-abc123` |

---
[Back to Overview](./OVERVIEW.md)
