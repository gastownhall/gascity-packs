# External Tool Integration

### LM Studio Integration

The `.tools/` module integrates with LM Studio for local LLM inference:

| Script | Purpose |
|:-------|:--------|
| `check_lm_studio_connection.sh` | Validates connectivity to the LM Studio API; checks endpoint availability and model loading status |
| `evaluate_lm_studio_model.sh` | Runs evaluation prompts against loaded models; tests completion, code generation, instruction following |
| `get_lm_studio_logs.sh` | Retrieves LM Studio server logs via SSH; useful for debugging inference issues on remote GPU hosts |

### LM Studio Configuration

| Variable | Purpose |
|:---------|:--------|
| `LM_STUDIO_HOST_IP` | Server hostname or IP |
| `LM_STUDIO_PORT` | API port (default 1234) |
| `LM_STUDIO_SSH_USER`, `LM_STUDIO_SSH_PASS` | SSH credentials for log retrieval |
| `LM_STUDIO_TEST_MODEL` | Model identifier for evaluation |

### Integration Module Contract

Integration modules in `.tools/` follow **relaxed stability guarantees**. They may:

- Change interfaces between minor versions.
- Add required environment variables.
- Depend on external services being available.

**Production workflows requiring stability should copy integration modules into project-specific tooling** rather than depending on the `.tools/` path directly.

---
[Back to Overview](./OVERVIEW.md)
