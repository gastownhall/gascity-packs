# Cron and Background Processing

### WP-Cron

WordPress cron triggers on **page loads, not system clock**. Low-traffic sites experience delayed execution. High-traffic sites experience stampedes. **For production, disable the page-load trigger (`DISABLE_WP_CRON = true`) and invoke `wp-cron.php` via system cron at a 1-5 minute interval.** This provides predictable timing and eliminates per-request overhead.

### Scheduled Event Patterns

- Register recurring events with `wp_schedule_event()` in **activation hooks**.
- Check `wp_next_scheduled()` before scheduling to prevent duplicates.
- **Unschedule in deactivation** with `wp_clear_scheduled_hook()`.
- Custom intervals register via `cron_schedules` filter.
- **Use Action Scheduler for high-volume processing** — persistent queues, failure tracking, retry logic, concurrency limits.

**Every cron callback must be idempotent.** WP-Cron provides no deduplication. **If a cron event fires twice, the handler must produce correct results both times.**

### Action Scheduler for Heavy Workloads

Action Scheduler is preferred for background processing exceeding simple cron. It stores pending actions in the database, uses claim-based processing to prevent duplicate execution, supports async immediate dispatch, and provides admin UI for monitoring.

| Function | Use |
|:---------|:----|
| `as_schedule_single_action()` | Deferred tasks |
| `as_schedule_recurring_action()` | Repeating jobs |
| `as_enqueue_async_action()` | Fire-and-forget processing |

**Group related actions for batch management.**

---
[Back to Overview](./OVERVIEW.md)
