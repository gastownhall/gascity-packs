# Missing remote in the full-build fixture

Baseline 005 reached the implementation worktree stage, which explicitly requires
`origin/HEAD`, fetches the remote default branch, and creates a detached worktree
from that remote tip. The harness created the fixture with `git init`, without a
remote. Bead fi-2qf therefore closed with `gc.outcome=fail` and
`gc.failure_class=missing-remote`. This is a harness precondition failure, not a
Beads/Gas City version incompatibility.

The next-run preflight clones the initial fixture into a bare repository inside
the same disposable runtime, adds it as origin, fetches it, resolves origin/HEAD,
and checks that the remote tip equals the initial fixture commit. It refuses to
reuse an existing origin or overwrite an existing remote repository. No GitHub
repository or user remote is changed, and no network remote is required.

The new regression uses a non-main default branch, verifies the local remote,
and executes the real workflow's fetch and detached-worktree commands. The
[red log](red.log) and [18 passing harness tests](green.log) are retained.
Baseline 005 remains unchanged; this correction cannot retroactively turn it
into a successful build or an A/B sample. Another full run is needed to validate
the remaining workflow.

A separate observation in the same run is that an implementation worker was
handed a do-work workflow latch and closed it without implementing the task.
The transcript and [blocker record](../../build-baseline-005/run-001-baseline/implementation-blocker.json)
preserve this behavior. Its routing cause has not been isolated; do not claim
that providing origin fixes it.
