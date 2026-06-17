Map the blast radius of a proposed code change — describe the impact
surface (callers, config field reach, concurrency, lifecycle) without
making any modifications.

This dispatches a coding agent to a rig with the `mol-pr-blast-radius`
formula. The agent maps callers, traces config-field chains, surfaces
concurrency contexts, and writes a structured report to
`.gc/pr-pipeline/blast-radius/<key>.md`. **No code is written.**

Usage:
  gc <binding> pr blast-radius "<scope>" [flags]

Arguments:
  <scope>             Free-text description of what the change will
                      touch. Examples:
                        "FuncXYZ in pkg/foo and the FieldBar struct"
                        "the cache reload path and its callers"
                        "issue 1234"

Flags:
  --rig <name>        Rig to analyze inside (defaults to $GC_RIG).
  --agent <name>      Worker agent name (default: "polecat").
  --key <id>          Output filename stem under
                      .gc/pr-pipeline/blast-radius/<key>.md.
                      Defaults to a slug derived from <scope>.

Examples:
  gc <binding> pr blast-radius "FuncXYZ in pkg/foo" --rig api-server
  gc <binding> pr blast-radius "the cache reload path" --key cache-reload

Direct sling (skip this command):
  gc sling api-server/polecat mol-pr-blast-radius --formula \
      --var scope="FuncXYZ in pkg/foo" --var key=funcxyz

Output:
  Report at <repo-root>/.gc/pr-pipeline/blast-radius/<key>.md
  Root-bead notes record `report_path:`.
