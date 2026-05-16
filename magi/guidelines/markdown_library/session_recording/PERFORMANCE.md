# Performance Impact

Session recording SDKs observe DOM mutations, capture user events, serialize page state, and transmit data to a backend. Each operation consumes CPU, memory, and network bandwidth on the user's device. **Performance impact must be measured, bounded, and acceptable.**

### Async SDK Loading

Load the recording SDK asynchronously and defer initialization until after the critical rendering path completes. The SDK must not:

- Block page load.
- Delay Largest Contentful Paint (LCP).
- Increase Interaction to Next Paint (INP).

Use dynamic `import()` or the SDK's async loading pattern. Verify with **Lighthouse and real-user monitoring** that the SDK does not regress Core Web Vitals.

### Footprint Measurement

Measure the SDK's CPU and memory footprint in production conditions:

| SDK | Approximate size |
|:----|:-----------------|
| OpenReplay tracker | ~26KB Brotli compressed |
| FullStory | Larger |
| LogRocket | Larger |

Monitor long task duration in the presence of the recording SDK. If the SDK contributes to long tasks (>50ms) or increases INP beyond the 200ms threshold:

1. Reduce mutation capture frequency.
2. Disable canvas recording.
3. Reduce network capture.
4. Switch to a lighter-weight SDK if necessary.

### Network Transmission Batching

SDKs should **batch and compress** recording data before transmission rather than sending individual events. Verify the SDK uses efficient protocols:

- WebSocket
- Beacon API
- Batched POST with compression

Monitor network request count and payload size from the SDK in DevTools. **A well-configured SDK adds fewer than 5 requests per minute and under 50KB/minute of upload bandwidth** for typical sessions.

### Feature Disablement

Disable recording features not needed for the analysis objective:

- Canvas recording
- WebGL capture
- iframe recording

If the analysis focuses on form interactions and navigation patterns, disable media capture entirely. Feature-level configuration reduces both CPU overhead and data volume.

---
[Back to Overview](./OVERVIEW.md)
