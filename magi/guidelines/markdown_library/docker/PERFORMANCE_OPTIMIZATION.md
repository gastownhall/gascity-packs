# Performance Optimization

### Startup Optimization

Maximum container startup time: 30 seconds.

.NET tiered JIT and ReadyToRun:
```dockerfile
ENV DOTNET_TieredPGO=1
ENV DOTNET_ReadyToRun=1
ENV DOTNET_TC_QuickJitForLoops=1
```

### Image Size Reduction Techniques

- Multi-stage builds.
- Distroless or Alpine base images.
- Static compilation when possible.
- Layer squashing for legacy applications.
- Combine `RUN` instructions and clean up in the same layer.

---
[Back to Overview](./OVERVIEW.md)
