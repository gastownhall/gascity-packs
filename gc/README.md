# GC Planning Skills

This pack provides a convoy-first planning and implementation workflow for Gas
City work:

- `gc.gather-requirements` gathers requirements and writes `requirements.md`.
- `gc.plan-implementation` turns approved requirements into an implementation plan and writes `implementation-plan.md`.
- `gc.create-beads` turns an approved implementation plan into a convoy/bead task plan, then
  creates convoys and runnable beads.
- `gc.implement` runs implementation for an approved convoy without the full
  build loop.
- `gc.gap-analysis` and `gc.review` produce targetless verdict reports.
- `gc.build` runs the full front-half approval flow and launches durable
  `build-run` for implement, gap-analysis/fix, review/fix, final reporting, and
  optional publish.
- `gc.gh-issue-triage`, `gc.gh-pr-review`, and `gc.gh-issue-fix` adapt
  canonical GitHub issue/PR URLs into the generic gc workflows.

Import it with the `gc` binding:

```toml
[imports.gc]
source = "../gascity-packs/gc"
```

Run the skills manually in order:

```text
Use skill gc.gather-requirements
Use skill gc.plan-implementation
Use skill gc.create-beads
```

Then launch implementation against the created implementation convoy:

```sh
gc sling <coordinator-target> implement --formula \
  --target <convoy-id> \
  --var context_path=<optional-context-yaml> \
  --var drain_policy=separate
```

Every formula in this pack uses `contract = "graph.v2"`. Targeted formulas take
the core-injected reserved convoy target; they do not declare `issue`,
`bead_id`, or `convoy_id` variables. `drain_policy=separate` is the standalone
default. Use `same-session` only when preserving one shared worktree and
conversation is explicitly desired and core shared drain support is available.

By default artifacts go under the target rig:

```text
<rig-root>/plans/<plan-slug>/
  requirements.md
  implementation-plan.md
  tasks.md
  context.yaml
  build/final-report.md
```

Each skill may use a different artifact root when the user explicitly asks for
one. The same `<plan-slug>/` structure should be used under the override root.

`gc.create-beads` uses `assets/scripts/create_beads_from_tasks.py` after approval.
The script requires Python 3 with PyYAML available, invokes `gc bd --rig
<target_rig>` for runnable beads, invokes `gc convoy --rig <target_rig>` for
convoy heads and membership, and records the created mapping in `tasks.md`.

The `tasks.md` payload uses nested `convoys[]` and `beads[]`; `epics[]` is a
hard validation error. `convoys[].dependencies` expands to runnable bead edges
from the upstream terminal runnable beads to the downstream root runnable beads.

Context bundles are YAML or JSON files with:

```yaml
items:
  - name: Requirements
    path: requirements.md
    description: Product requirements and acceptance criteria.
```

Each item has only `name`, `path`, and `description`. Validate with:

```sh
python3 <pack-root>/assets/scripts/validate_context_bundle.py context.yaml --allow-root <artifact-root>
```

Gap-analysis and review reports use `schema: gc.verdict-report.v1` front matter
with `verdict: pass|fail`. Validate with:

```sh
python3 <pack-root>/assets/scripts/validate_verdict_report.py report.md --kind review
```

## GitHub Adapter Workflows

The GitHub workflows are targetless `graph.v2` formulas. They accept only full
canonical URLs:

```text
https://github.com/<owner>/<repo>/issues/<number>
https://github.com/<owner>/<repo>/pull/<number>
```

Launch triage:

```sh
gc sling <coordinator-target> github-issue-triage --formula \
  --var github_issue_url=https://github.com/<owner>/<repo>/issues/<number>
```

Launch PR review:

```sh
gc sling <coordinator-target> github-pr-review --formula \
  --var github_pr_url=https://github.com/<owner>/<repo>/pull/<number> \
  --var post_mode=human_gate
```

Launch issue fix:

```sh
gc sling <coordinator-target> github-issue-fix --formula \
  --var github_issue_url=https://github.com/<owner>/<repo>/issues/<number> \
  --var mode=interactive \
  --var pr_mode=none
```

GitHub API calls go through wrapper scripts in
`<pack-root>/assets/scripts/`. Formulas should call those wrappers, not `gh`
directly, except when diagnosing wrapper failures.
