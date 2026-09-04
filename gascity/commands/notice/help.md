Send, acknowledge, and reconcile durable role-addressed notices.

Usage:

```text
gc gc notice send --to-role <role> --work-ref <bead-or-pr> \
  --state-fingerprint <immutable-state> --subject <summary> --message <body>
gc gc notice ack <notice-id> --disposition <accepted|dismissed|superseded>
gc gc notice reconcile [--limit <1-100>] [--retention-seconds <seconds>]
```

`send` records a durable mail receipt before it reports acceptance. `ack` is a
recipient-role guardrail: it reads and archives that receipt before recording
the supplied disposition. `reconcile` is a bounded maintenance operation; it
checks canonical-role routability and escalates to a human only after five
minutes without a routable role.
