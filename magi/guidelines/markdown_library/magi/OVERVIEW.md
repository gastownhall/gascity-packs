---
version: "0.1.0"
pack: "magi"
schema: 2
topics:
  - deploy
  - analyze
  - improve
  - doctor
  - beads
  - molecule
  - utilities
---

# Magi Guidelines — Index

The magi pack unifies five model-runtime deployers (claude, codex, gemini, openai) plus the project_analyzer tool behind a single twelve-verb surface. These guidelines are the authoritative source the orchestrator scripts load at runtime via `magi_common.load_policy(topic)`. Every script reads its corresponding topic file and enforces the documented constants.

## Topics

| File | Covers | Loaded by |
|---|---|---|
| [deploy.md](deploy.md) | Install + uninstall: target resolution, backup policy, idempotency, rollback, secrets, env precedence | `magi_install.py`, `magi_uninstall.py` |
| [analyze.md](analyze.md) | Bottom-up traversal, ignore list, source-SHA-256 idempotency, LM Studio prereq | `magi_analyze.py` |
| [improve.md](improve.md) | Three-model pipeline contract, resume semantics, scope flags | `magi_improve.py` |
| [doctor.md](doctor.md) | Exit-code semantics (0 ok / 1 fail / 2 warn), per-check severity promotion | `magi_doctor.py` |
| [beads.md](beads.md) | Label taxonomy, value domains, timeouts, hook contracts | `magi_status.py`, hook scripts |
| [molecule.md](molecule.md) | Bootstrap chain, on-failure semantics, worst-child rc propagation | `magi_molecule.py` |
| [utilities.md](utilities.md) | Portable `.utilities/` integration via `setup_utilities.sh`; no rsync | `magi_bootstrap_project.py`, `check-utilities.sh` |

## Verb-to-topic map

| Verb | Topic file |
|---|---|
| `install` | `deploy.md` |
| `uninstall` | `deploy.md` (Rollback section) |
| `analyze` | `analyze.md` |
| `improve` | `improve.md` |
| `doctor` | `doctor.md` |
| `status` | `beads.md` (bd lifecycle), `deploy.md` (state.json schema) |
| `molecule` | `molecule.md`, `beads.md` |
| `bootstrap-project` | `utilities.md` |
| `remember` | `beads.md` |
| `recall` | `beads.md` |
| `ready` | `beads.md` |
| `formulas` | `molecule.md` |

Topic files are self-contained; reading one does not require reading siblings. This OVERVIEW indexes them and carries no rule content.
