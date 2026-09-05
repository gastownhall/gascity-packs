Acknowledge an inspected interrupted turn

gc bb recover --thread <BB-thread-ID> --confirm-reviewed

First read the remote transcript in Gas City. This command verifies idle/non-degraded state with no pending tools/interactions, then acknowledges unseen output so BB can resume. It does not replay history or resend any prompt. It cannot repair ambiguous session creation or a process-crash lock; inspect those receipts manually.
