# Changelog

All notable changes to contributing-to-gascity are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.5.0] — Pack renamed `contributing` → `contributing-to-gascity`

Breaking. The pack directory and identity moved from `contributing` to
`contributing-to-gascity`, naming its target city explicitly and
disambiguating it from the generic contribution activity. Adopters must
update any `[imports.contributing]` table to `[imports.contributing-to-gascity]`
and the `source` path accordingly — this is an import-path break, no behavior
change.

### Changed

- `pack.toml`: `name` → `contributing-to-gascity`; `version` 0.4.0 → 0.5.0.
- Registry `source` → `https://github.com/gastownhall/gascity-packs//contributing-to-gascity`.
- Import-path, directory, and test-command references updated across the pack
  README and the repo catalog.

### Unchanged

- Every skill name (`start-contribution`, `find-work`, `plan-implementation`,
  `map-blast-radius`, `fine-tune`, `review`, `write-issue`,
  `orchestrate-contribution`) and every `mol-contributing-*` formula ID — these
  name the lifecycle action, not the pack directory.
- Formula output paths (`.gc/contributing/`) and all baked-in standards (the
  B-rule adoption audit, blast-radius dimensions, test tiers, gating model).
