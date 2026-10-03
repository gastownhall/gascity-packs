# Changelog

All notable changes to contributing-to-gascity are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.5.0] — Pack renamed `contributing` → `contributing-to-gascity`

Breaking. The pack directory and identity moved from `contributing` to
`contributing-to-gascity`, naming its target city explicitly and
disambiguating it from the generic contribution activity. Adopters must update
the import table and source path. This is an import-path break with no behavior
change.

### Changed

- `pack.toml`: `name` → `contributing-to-gascity`; `version` 0.4.0 → 0.5.0.
- Registry source → `https://github.com/gastownhall/gascity-packs/tree/main/contributing-to-gascity`.
- Import-path, directory, and test-command references updated across the pack
  README and repository catalog.

### Unchanged

- Every skill name and every `mol-contributing-*` formula ID; these name the
  lifecycle action, not the pack directory.
- Formula output paths under `.gc/contributing/` and all baked-in standards.
