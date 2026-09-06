Reconcile an inspected interrupted operation

gc bb recover --thread <BB-thread-ID> --confirm-reviewed

Release the thread in BB and read the complete remote transcript in Gas City first. Recovery resolves the original deterministic creation alias and correlates the recorded submit result with a new prompt and completed answer in reliable idle history. It acknowledges unseen output; it does not replay history or resend prompts.

If the submit HTTP response was lost, supply --request-id <original-GC-request-ID> --event-cursor <original-cursor> from inspected GC events. Both are required; unrelated requests cannot establish completion. Older receipts without prompt evidence remain blocked.

A live journal owner blocks recovery. A dead process on this host permits automatic lock retirement, preserving the old lock. Unknown, corrupt, or foreign-host locks require manual inspection; preserve the journal and restore its original host before continuing.
