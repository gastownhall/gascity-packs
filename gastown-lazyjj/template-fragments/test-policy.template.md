{{ define "test-policy" }}
## Test Policy

Focused tests only. Do not run full test suites, repo-wide builds, repo-wide
linters, broad quality gates, or any other sweeping verification unless the
human explicitly asks for that exact command.

Default verification is limited to the narrowest focused check tied directly to
the specific bead and the files you changed. If no focused affected-test
command is configured, stop and ask for one before submitting.

Unrequested broad-suite failures are not valid rejection evidence. They must
not be used to reject, block, bounce, or escalate a bead. Record them only as
incidental observations if they appear while running a human-requested command.
{{ end }}
