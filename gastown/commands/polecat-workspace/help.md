# gc gastown polecat-workspace

Deterministically creates or recovers a polecat task artifact, establishes the
canonical task branch, synchronizes its lease, runs the Graph-v2 setup command,
records a durable receipt, and completes the exact workspace step.

```text
gc gastown polecat-workspace execute
```

The command derives its source, convoy, root variables, artifact, branch, and
runtime identity from authoritative city state. It accepts no model-supplied
workspace arguments.

Project setup is serialized by an exact generation lock held from intent
inspection through done publication. A crashed owner may be replaced only
after the lock is released. Receipt-free intent is provably pre-execution and
can be adopted; a nonempty setup command with a durable `attempted` receipt is
ambiguous and is quarantined for explicit reconciliation without re-execution.
An empty setup command can safely recover either state and complete its receipt.

Exit status `0` means the exact workspace step is durably complete. Exit status
`64` means an unsafe state was durably quarantined, read back exactly, and
reported to Witness. Exit status `75` means the state is indeterminate but
preserved and the same command may be retried after the diagnostic is
addressed.
