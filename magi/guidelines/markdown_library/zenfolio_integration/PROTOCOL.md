# API Protocol and Request Format

The Zenfolio API supports two wire protocols: **SOAP (XML)** and **JSON-RPC**. Both hit the same endpoint and expose identical methods.

### Protocol Selection

| Protocol | Use |
|:---------|:----|
| **JSON-RPC** | All new integrations. Smaller payloads, faster JS/TS parsing, integrates naturally with modern frontend stacks |
| **SOAP** | Legacy integrations only |

JSON-RPC requests:

- `Content-Type: application/json`.
- Body: `{ "method": "MethodName", "params": [...] }`.

### Response Handling

JSON-RPC responses return:

```json
{ "result": ... }       // success
{ "error": { "code": ..., "message": ... } }  // failure
```

**Always check for the `error` field before accessing `result`.** A 200 HTTP status with a JSON-RPC error in the body is a successful HTTP request that returned an application-level error. **Do not rely on HTTP status codes alone for error detection with JSON-RPC.**

### Method Names and Parameters

- **Method names and parameter order are case-sensitive.** `LoadPhotoSet` is not `loadPhotoSet`.
- **Params are positional arrays, not named objects.** Passing parameters out of order produces incorrect results or errors.
- **Refer to the official API reference** for exact method signatures, parameter order, and parameter types for every call.

### IncrementalLevel

Use the `IncrementalLevel` parameter on `Load` methods (`LoadPhotoSet`, `LoadPhoto`, `LoadGroup`) to control response size:

| Level | Returns |
|:------|:--------|
| `Level1` | Core fields |
| `Level2` | Adds caption, keywords, categories |
| `Full` | All fields including parent groups and byte counts |

**Request the minimum level needed for the operation.** `Full`-level responses for large galleries with hundreds of photos are significantly larger than `Level1` responses.

---
[Back to Overview](./OVERVIEW.md)
