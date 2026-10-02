# Jev build A/B report

## Runs

| Run | Arm | Workload | Build | Harness status | Review gate | Hidden pass | Minutes | Requests | Output tokens | Skipped lanes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ab-003/run-001-baseline-slugify | baseline | slugify | completed | completed | - | yes | 28.8 | 198 | 43,802 | - |
| ab-003/run-002-jev-slugify | jev | slugify | completed | completed | jev | yes | 14.3 | 116 | 25,261 | test_evidence |
| ab-003/run-003-jev-durations | jev | durations | completed | completed | jev | yes | 12.8 | 129 | 27,693 | test_evidence |
| ab-003/run-004-baseline-durations | baseline | durations | completed | completed | - | yes | 30.6 | 276 | 70,469 | - |
| ab-003/run-007-jev-schema-roots | jev | schema-roots | completed | completed | jev | no | 31.6 | 170 | 41,540 | test_evidence |
| ab-003/run-009-jev-slugify | jev | slugify | completed | completed | jev | yes | 13.2 | 119 | 24,360 | test_evidence |
| ab-003/run-010-baseline-slugify | baseline | slugify | completed | completed | - | yes | 22.5 | 198 | 44,524 | - |
| ab-003/run-011-baseline-durations | baseline | durations | completed | completed | - | yes | 31.1 | 206 | 55,367 | - |
| ab-003/run-012-jev-durations | jev | durations | completed | completed | jev | yes | 12.8 | 113 | 25,849 | test_evidence |
| ab-003/run-013-jev-legacy-work-options | jev | legacy-work-options | completed | completed | jev | yes | 20.2 | 191 | 47,169 | test_evidence |
| ab-003/run-014-baseline-legacy-work-options | baseline | legacy-work-options | completed | completed | - | no | 29.3 | 327 | 84,690 | - |
| ab-003/run-015-baseline-schema-roots | baseline | schema-roots | completed | completed | - | yes | 40.5 | 292 | 82,393 | - |
| ab-003/run-016-jev-schema-roots | jev | schema-roots | completed | completed | jev | yes | 23.2 | 192 | 48,467 | test_evidence |
| ab-003-rerun-legacy/run-001-baseline-legacy-work-options | baseline | legacy-work-options | completed | completed | - | no | 40.5 | 321 | 89,203 | - |
| ab-003-rerun-legacy/run-002-jev-legacy-work-options | jev | legacy-work-options | completed | completed | jev | no | 18.4 | 185 | 46,383 | - |
| ab-003-rerun-schema/run-001-baseline-schema-roots | baseline | schema-roots | completed | completed | - | yes | 31.2 | 304 | 82,486 | - |

## Means by workload and arm

| Workload | Arm | Runs | Hidden pass | Minutes | Requests | Input+cache tokens | Output tokens |
| --- | --- | --- | --- | --- | --- | --- | --- |
| durations | baseline | 2 | 2/2 | 30.8 | 241.0 | 18,552,016 | 62,918 |
| durations | jev | 2 | 2/2 | 12.8 | 121.0 | 9,163,249 | 26,771 |
| legacy-work-options | baseline | 2 | 0/2 | 34.9 | 324.0 | 26,298,940 | 86,946 |
| legacy-work-options | jev | 2 | 1/2 | 19.3 | 188.0 | 15,056,351 | 46,776 |
| schema-roots | baseline | 2 | 2/2 | 35.8 | 298.0 | 24,192,024 | 82,440 |
| schema-roots | jev | 2 | 1/2 | 27.4 | 181.0 | 14,367,121 | 45,004 |
| slugify | baseline | 2 | 2/2 | 25.6 | 198.0 | 15,161,281 | 44,163 |
| slugify | jev | 2 | 2/2 | 13.7 | 117.5 | 8,969,178 | 24,810 |

## Mean requests and output tokens per stage, backlog workloads

| Stage | baseline requests | baseline output | jev requests | jev output |
| --- | --- | --- | --- | --- |
| prepare | 9.0 | 2,047 | 9.5 | 2,127 |
| requirements | 17.0 | 5,279 | 20.0 | 5,461 |
| plan | 18.2 | 5,961 | 0.0 | 0 |
| plan-review | 7.2 | 1,286 | 0.0 | 0 |
| decompose | 19.8 | 5,427 | 22.8 | 5,402 |
| implement | 113.0 | 30,381 | 56.5 | 14,540 |
| summarize | 18.5 | 6,220 | 14.8 | 4,435 |
| review | 96.5 | 26,201 | 59.8 | 13,823 |
| publish | 5.0 | 835 | 0.0 | 0 |
| helpers | 6.8 | 1,056 | 1.2 | 102 |
| total | 311.0 | 84,693 | 184.5 | 45,890 |

## Mean requests and output tokens per stage, planted workloads

| Stage | baseline requests | baseline output | jev requests | jev output |
| --- | --- | --- | --- | --- |
| prepare | 9.8 | 1,892 | 10.0 | 2,185 |
| requirements | 10.5 | 3,408 | 0.0 | 0 |
| plan | 11.0 | 3,463 | 0.0 | 0 |
| plan-review | 6.8 | 856 | 0.0 | 0 |
| decompose | 19.0 | 4,270 | 0.0 | 0 |
| implement | 65.2 | 13,770 | 50.2 | 9,930 |
| summarize | 16.5 | 5,095 | 0.0 | 0 |
| review | 75.5 | 19,890 | 58.5 | 13,607 |
| publish | 4.0 | 806 | 0.0 | 0 |
| helpers | 1.2 | 91 | 0.5 | 69 |
| total | 219.5 | 53,540 | 119.2 | 25,791 |

## Jev decisions, all runs

Act means Jev decided alone; confirm and escalate left the call to Claude or the full path. Right and wrong count labeled act decisions checked against a lane verdict or the finished diff.

| Decision | Act | Confirm | Escalate | Labeled | Jev right | Jev wrong | Misses |
| --- | --- | --- | --- | --- | --- | --- | --- |
| intake.compact | 4 | 0 | 0 | 4 | 4 | 0 | 0 |
| intake.direct | 4 | 0 | 0 | 4 | 4 | 0 | 0 |
| review.criterion | 17 | 25 | 0 | 26 | 1 | 0 | 0 |
| review.test_evidence | 8 | 0 | 0 | 1 | 1 | 0 | 0 |
| smell.clean | 6 | 2 | 0 | 3 | 1 | 0 | 0 |
