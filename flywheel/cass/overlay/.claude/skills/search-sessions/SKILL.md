# /search-sessions — Search past agent sessions

Use `cass` to search past coding-agent sessions for relevant solutions,
debugging history, and prior decisions.

Never run bare `cass` in an agent context. Use non-interactive mode only.

## Preflight

```bash
cass health --json || cass index --full
```

## Find relevant sessions

Current workspace and recent matches:

```bash
cass sessions --current --json
cass sessions --workspace "$(pwd)" --json --limit 5
```

Direct search:

```bash
cass search "error message or subsystem" --json --limit 5 --fields minimal
```

## Inspect a hit

Use `source_path` and `line_number` from search output:

```bash
cass view <source_path> -n <line_number> --json
cass expand <source_path> -n <line_number> -C 3 --json
```

## If expected history is missing

```bash
cass diag --json
```

## Tips

- Start with an exact error string, workspace path, or subsystem name.
- Use `--fields minimal` first, then inspect only the strongest hits.
- Check prior sessions before re-debugging an unfamiliar failure.
