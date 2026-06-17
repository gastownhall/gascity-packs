Plan a PR for an issue — front-load the analysis a maintainer's adoption
review will check, before any code is written.

This dispatches a coding agent to a rig with the `mol-pr-start` formula.
The agent reads the issue, runs BLOCKING gates (competing-PR and
architectural-refactor checks), maps blast radius, checks the repo's
conventions, produces a structured plan saved to
`.gc/pr-pipeline/plans/issue-<N>.md`, and audits the plan against 19
recurring review findings. **No code is written.**

Usage:
  gc <binding> pr plan <issue-number> [flags]

Arguments:
  <issue-number>      Integer issue number on the rig's GitHub repo.

Flags:
  --rig <name>        Rig to plan inside (defaults to $GC_RIG if set).
  --agent <name>      Agent name to sling to (default: "polecat").
                      Set this if your city's coding-worker pool uses
                      a different name (e.g. "claude", "worker").

Examples:
  # Inside a rig session (GC_RIG is set automatically):
  gc <binding> pr plan 1234

  # Explicitly target a rig:
  gc <binding> pr plan 1234 --rig api-server

  # Use a non-polecat worker:
  gc <binding> pr plan 1234 --rig api-server --agent claude

Direct sling (skip this command):
  gc sling api-server/polecat mol-pr-start --formula --var issue=1234

Output:
  The plan is written to <repo-root>/.gc/pr-pipeline/plans/issue-<N>.md.
  The molecule's root bead notes record the plan path under `plan_path:`,
  or a block reason if a BLOCKING gate triggered.

Environment variables (set by gc):
  GC_CITY_PATH      absolute city root
  GC_PACK_DIR       absolute pack directory
  GC_PACK_NAME      pack name ("pr-pipeline")
  GC_CITY_NAME      city workspace name
  GC_RIG            current rig name (when running inside a rig session)
