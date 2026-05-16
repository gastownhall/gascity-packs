# Performance and GC Tuning

### Garbage Collector Selection

| GC | Use For | Pros |
|:---|:--------|:-----|
| **G1GC** (default in Java 17) | Most workloads, heaps 4–64GB+ | Best balance of throughput, latency, pause time |
| **ZGC** | Sub-millisecond pauses, large heaps | Production-ready in Java 17 |
| **Parallel GC** | Batch processing | Throughput over pause time |

Enable G1: `-XX:+UseG1GC`. Enable ZGC: `-XX:+UseZGC`.

### Java Flight Recorder in Production

```text
-XX:StartFlightRecording=disk=true,maxsize=500m,dumponexit=true
```

Captures GC events, lock contention, method profiling, I/O operations, memory allocation with less than 1% overhead. Analyze with JDK Mission Control or IntelliJ's profiler.

### String Deduplication

Enable `-XX:+UseStringDeduplication` with G1GC for applications with high string duplication (web servers, data processors). Reduces memory usage by 10–30% in string-heavy applications.

### Measure Before Optimizing

Use JMH (Java Microbenchmark Harness) for micro-benchmarks. Use JFR and APM tools (New Relic, Datadog, Elastic APM) for production profiling. **Do not optimize based on assumptions.**

### Heap Sizing

Set initial and maximum heap sizes equal (`-Xms` = `-Xmx`) for server workloads. Eliminates heap resizing pauses during warmup. Size based on observed live data set plus headroom for GC overhead — typical starting point is 2–4× the live data set.

---
[Back to Overview](./OVERVIEW.md)
