# Prohibited Practices

### Never Do

- Implement `GatewayModuleHook` / `DesignerModuleHook` / `ClientModuleHook` interfaces directly — extend the `Abstract*ModuleHook` classes.
- Perform RPC calls, database queries, tag I/O, or any blocking work on the EDT — use `SwingWorker`, `Task`, or background threads.
- Leave registered listeners, scheduled tasks, sinks, bundles, or extension points uncleaned in `shutdown`.
- Scope jars `GCD` by default — audit every jar; Gateway-only code in `G`, Vision shared in `CD`.
- Hardcode user-visible English strings — use `BundleUtil.get().getString`.
- Let an `SRConnection` escape its try-with-resources block.
- Concatenate user input into SQL — use `runPrepQuery` / `runPrepUpdate` with `?` placeholders.
- Use `System.out.println` or `printStackTrace` — use SLF4J via `LoggerFactory.getLogger(getClass())`.
- Ship an unsigned `.modl` for production distribution.
- Commit keystores or signing passwords — use environment variables or secret mounts.
- Omit `serialVersionUID` on `Serializable` classes used in RPC or push notifications.

---
[Back to Overview](./OVERVIEW.md)
