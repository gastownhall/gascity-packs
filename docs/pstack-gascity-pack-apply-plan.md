# PStack dest-env apply how-to

Production sequencing lives in `docs/pstack-production-readiness-plan.md`. This page is the dest-env archive command. It is not a GitHub PR.

## Host command

From a host shell outside bubblewrap, with dest-env writable.

```sh
python pstack/scripts/apply_intent_change.py \
  --source <dest-env>/openspec/changes/audit-pstack-gascity-pack-contracts \
  --dest <dest-env> \
  --archive
```

`--source` is required and must sit outside `pstack/`. Dest-env owns the change payload. This pack does not ship dest-env or `.work/`.

## You see

- `openspec validate audit-pstack-gascity-pack-contracts --type change --strict` prints that the change is valid before archive.
- dest-env live swarm THEN contains sequential `frame`, `fanout`, and `fanin`.
- `refresh-pstack-pack-source-and-formula-requirements` stays an active change.

## This sandbox

This TUI cannot write dest-env `openspec/`. Host dest-env archive stays unproven.
