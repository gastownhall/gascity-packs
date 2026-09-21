# Duplicate investigation order

No duplicate verdict is supplied. Investigate candidates before applying the existing triage policy.

## Source issue
Daily job fires twice across DST
At the autumn DST transition, a daily 01:30 job executes twice for the repeated local time.

## Candidate 1: C2
Autumn repeated hour duplicates a run
A scheduled daily 01:30 run executes twice during the fall clock rollback.

## Candidate 2: C1
Daily job skipped in spring
At the spring DST transition, 02:30 does not exist and the daily job is skipped.

## Candidate 3: C3
UTC display
Show UTC timestamps in the audit UI.
