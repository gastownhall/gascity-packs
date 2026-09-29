This is the `implementation-base` methodology contract source-anchor close
step.

Concrete methodology packs override this step only when they need additional
artifact checks. Verify the implementation result and close the source anchor
before this workflow step closes pass. If `{{summary_path}}` is set, write or
verify the per-item implementation summary there before closing.
