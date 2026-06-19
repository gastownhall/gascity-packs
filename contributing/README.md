# Contributing

The external-contributor lifecycle for
[gastownhall/gascity](https://github.com/gastownhall/gascity), distributed as a
Gas City pack.

It gives an outside contributor the full journey of landing work upstream — and
routes each step to the command that runs it.

## The lifecycle

| Step | What you do | Command | Owned by |
|------|-------------|---------|----------|
| 1 | Write a high-quality issue | `write-issue` skill (this pack) | **contributing** |
| 2 | Find a priority issue to work on | `gc sling <rig>/<agent> mol-pr-triage --formula` | pr-pipeline |
| 3 | Plan & build the PR | `gc pr-pipeline pr plan <issue>` + `pr blast-radius` | pr-pipeline |
| 4 | Self-review before pushing | `gc pr-pipeline pr review <pr>` + `pr ship` | pr-pipeline |

Two entry points join the same loop:

- **PR a priority issue** — start at step 2 (triage to find work), then plan it.
- **PR your own issue** — start at step 1 (file the issue), then plan it.

The `contributing` skill is the operational map; it explains both entry points
and links each step to its command.

## Why it composes pr-pipeline

Steps 2-4 are already delivered by the
[pr-pipeline](../pr-pipeline) pack — its `mol-pr-triage`, `mol-pr-start`
(`pr plan`), `mol-pr-blast-radius` (`pr blast-radius`), `mol-pr-review`
(`pr review`), and `mol-pr-ship` (`pr ship`) formulas. This pack does **not**
re-implement them; it imports pr-pipeline and references those commands.

The one net-new piece is **step 1** — the `write-issue` skill, the
issue-authoring discipline that the pr-pipeline workflows assume has already
happened.

## Pairing

This pack pairs with `pr-pipeline`. The pairing is declared in `pack.toml`:

```toml
[imports.pr-pipeline]
source = "../pr-pipeline"   # path; or git URL when published
```

Repoint `source` to wherever your city vendors pr-pipeline. The `write-issue`
skill is fully self-contained and works on its own; the `contributing` lifecycle
skill is where the pr-pipeline commands come into play, so the full step 2-4
experience needs pr-pipeline available.

## Usage

In your city's `pack.toml`:

```toml
[imports.contributing]
source = "../packs/contributing"   # path; or git URL when published
```

Then the skills load for your coding agent, and the paired pr-pipeline commands
are available as `gc pr-pipeline pr ...`.

## Pack contents

```
contributing/
├── pack.toml                       schema=2; imports pr-pipeline
├── README.md
├── skills/
│   ├── contributing/SKILL.md       the lifecycle map (both entry points)
│   └── write-issue/SKILL.md        net-new: contributor issue-writing discipline
├── doctor/                         preflight checks (gc, gh, git present)
│   ├── check-gc.sh   + gc/doctor.toml
│   ├── check-gh.sh   + gh/doctor.toml
│   └── check-git.sh  + git/doctor.toml
└── tests/
    ├── test_skill_frontmatter.py   skills have name + description
    └── test_pack_structure.py      pairing declared; doctor scripts executable
```

## Tests

```sh
python3 -m pytest contributing/tests/
```
