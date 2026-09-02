## 1. Restamp Gherkin

- [x] 1.1 Keep the vendor Durable Gherkin AND as "another project".
- [x] 1.2 Keep the arm-list AND as plugin `skills/` only. Do not restore a `pstack/` ban.

## 2. Pack test (red)

- [x] 2.1 Add a pack test. `--source` of `openspec/changes/archive/2026-09-02-pstack-program-arm-list` without `--change` validates under name `pstack-program-arm-list`.

## 3. Apply name (green)

- [x] 3.1 Delete `DEFAULT_CHANGE` from `pstack/scripts/apply_intent_change.py`.
- [x] 3.2 Derive the change name from the `--source` directory name. Strip a leading `YYYY-MM-DD-` prefix when `--change` is omitted.
- [x] 3.3 Keep an explicit `--change` as the winner.

## 4. Program plan 1.1

- [ ] 4.1 Drop `--change pstack-program-arm-list` from the 1.1 boot recipe in `docs/pstack-program-plan.md`.
- [ ] 4.2 Change the 1.1 "44 passed" boxes to "45 passed".
- [ ] 4.3 Name archived `pstack-gherkin-restamp` in the land-honesty Build checkbox.
- [ ] 4.4 Add apply-script and pack-test files to the land-isolation file list.

## 5. Validate and archive

- [ ] 5.1 Validate with `--source` set to the payload tree outside dest `openspec/changes/pstack-gherkin-restamp`. Do not `--source` that dest path. `copy_change` deletes dest first.
- [ ] 5.2 Archive with `--archive` from that same outside source.
- [ ] 5.3 Run `uv run --with pytest --with pyyaml pytest -q pstack/tests/test_pstack_pack.py`.
