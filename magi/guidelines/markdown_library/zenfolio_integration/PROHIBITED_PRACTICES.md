# Prohibited Practices

### Never Do

- Expose the Zenfolio authentication token (`X-Zenfolio-Token`) in client-side JavaScript, HTML source, or browser-accessible storage.
- Embed Zenfolio username or password in client-side bundles, public environment variables, or version-controlled configuration.
- Use `AuthenticatePlain` in production. **Use challenge-response authentication.**
- Call mutating Zenfolio API methods (Create, Update, Delete, Upload) directly from client-side JavaScript.
- Include `UploadUrl`, `VideoUploadUrl`, or `RawUploadUrl` in proxy responses to the frontend.
- Serve original-resolution images (5000px+, multi-MB) for grid thumbnails or list views.
- Render content without checking `AccessDescriptor`. **Private galleries must not appear in public-facing UIs.**
- Let raw JSON-RPC error objects or stack traces propagate to the end user.
- Retry failed API calls indefinitely without maximum attempt limits or backoff.
- Make every frontend request hit the Zenfolio API directly without caching. **Cache is mandatory for production.**
- Hardcode gallery IDs in component source code. Store IDs in configuration, CMS, or database.
- Make Zenfolio API calls over HTTP (non-TLS). **All communication uses HTTPS.**
- Set the User-Agent header to a browser string. Use a descriptive application identifier.
- Always request `Full`-level data when `Level1` or `Level2` suffices. **Request the minimum data level needed.**
- Skip shakedown after a triggering change.
- Run shakedown against a recorded fixture, in-memory stub, or mocked Zenfolio API.
- Point shakedown downstream sync at production targets.
- Optimize during shakedown.

---
[Back to Overview](./OVERVIEW.md)
