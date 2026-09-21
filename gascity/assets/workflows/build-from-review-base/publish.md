This is the `build-from-review-base` publish stage.

Read push {{push}}, open_pr {{open_pr}}, and the finalized continuation outcome
from the workflow root metadata. If neither publishing action is explicitly
authorized, no-op and record `not_published`.

Publishing disabled or no-op status must never convert a blocked, failed, or
repairable finalization into a passing workflow outcome. Preserve
`gc.outcome=fail`, `gc.build.status=blocked`, `gc.failure_class`,
`gc.build.review_state`, `gc.build.repair_status`, and `gc.restart.*` metadata
when finalize recorded them.

If publishing is authorized but `gc.build.review_residual_required` is greater
than zero, do not push or open a PR: record
`gc.publish.status=publish_blocked_residual_findings` with the residual counts
and leave the workflow outcome unchanged.

If publishing is authorized, publish only after the continuation finalized
successfully and the review stage approved or explicitly allowed publication.
Record push status, PR status, or a blocked publish reason on the workflow root
and publish step before closing.
