# Scheduled Tasks

### Cron-Safe Scripts
Scripts intended for cron must:
- Use file locking to prevent concurrent runs.
- Not rely on environment variables set by interactive shells (PATH, HOME, etc.) — set them explicitly.
- Redirect all output to a log file.
- Use absolute paths for every binary and file reference.

### Scheduled Task Monitoring
Scheduled tasks should report start, completion, and failure status to an external monitoring endpoint or heartbeat service. A cron job that fails silently is invisible to the team. At minimum, log the outcome; preferably, send a webhook or touch a heartbeat URL.

---
[Back to Overview](./OVERVIEW.md)
