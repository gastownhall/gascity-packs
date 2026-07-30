Surface durable Gastown polecat block contracts for the Mayor.

Usage:

    gc gastown polecat-blocks surface

`surface` scans every status in the exact runtime rig store for rows carrying
`gc.polecat_block_version=1`. It bypasses the controller API/cache, validates
each source/step pair against its Graph-v2 root and exact input convoy, and also
surfaces partial or malformed contracts. Session liveness, including
quarantine, never suppresses a durable block.

Each exact block signature is canonicalized and stored as a fixed
`sha256:<64-hex>` digest, then mailed to `mayor/` at least once. Subjects and
diagnostic fields are control-free and byte-bounded; malformed bead metadata
is never copied wholesale into mail. Only after mail succeeds does the command
write and read back
`gc.polecat_block_alert_version` and
`gc.polecat_block_alert_signature` on the source row (or the surviving row of
a partial contract). A matching receipt suppresses repeat mail. A crash between
mail and receipt can duplicate a notification; it cannot silently lose one.

This command is deliberately not a recovery command. Other than the two alert
receipt fields, it never changes bead status, ownership, routing, workflow,
artifact, block provenance, or source/step outcome. Block resolution requires
a separate exact, explicitly authorized workflow-generation reset.
