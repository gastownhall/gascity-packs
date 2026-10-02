# Jev build A/B report

## Runs

| Run | Arm | Workload | Build | Harness status | Review gate | Hidden pass | Minutes | Requests | Output tokens | Skipped lanes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ab-002/run-001-baseline-slugify | baseline | slugify | completed | completed | - | yes | 22.5 | 216 | 50,822 | - |
| ab-002/run-002-jev-slugify | jev | slugify | completed | completed | jev | yes | 20.6 | 197 | 42,172 | test_evidence |
| ab-002/run-003-jev-durations | jev | durations | completed | completed | jev | yes | 11.8 | 116 | 25,892 | test_evidence |
| ab-002/run-004-baseline-durations | baseline | durations | completed | completed | - | yes | 21.0 | 224 | 58,058 | - |
| ab-002/run-005-baseline-legacy-work-options | baseline | legacy-work-options | completed | completed | - | no | 24.3 | 272 | 72,079 | - |
| ab-002/run-006-jev-legacy-work-options | jev | legacy-work-options | completed | completed | jev | yes | 20.1 | 219 | 55,903 | - |
| ab-002/run-007-jev-schema-roots | jev | schema-roots | completed | completed | jev | yes | 18.1 | 172 | 45,254 | test_evidence |
| ab-002/run-008-baseline-schema-roots | baseline | schema-roots | completed | completed | - | no | 35.2 | 378 | 97,584 | - |
| ab-002/run-009-jev-slugify | jev | slugify | completed | completed | jev | yes | 14.0 | 113 | 25,611 | test_evidence |
| ab-002/run-010-baseline-slugify | baseline | slugify | completed | completed | - | yes | 18.2 | 192 | 47,048 | - |
| ab-002/run-011-baseline-durations | baseline | durations | completed | completed | - | yes | 20.5 | 214 | 54,067 | - |
| ab-002/run-012-jev-durations | jev | durations | completed | completed | jev | yes | 11.5 | 117 | 23,728 | test_evidence |
| ab-002/run-013-jev-legacy-work-options | jev | legacy-work-options | completed | completed | jev | no | 19.6 | 207 | 50,298 | - |
| ab-002/run-014-baseline-legacy-work-options | baseline | legacy-work-options | completed | completed | - | no | 27.5 | 327 | 84,541 | - |
| ab-002/run-015-baseline-schema-roots | baseline | schema-roots | completed | completed | - | yes | 23.3 | 349 | 87,070 | - |
| ab-002/run-016-jev-schema-roots | jev | schema-roots | completed | completed | jev | no | 18.6 | 188 | 48,554 | test_evidence |
| ab-002/run-017-baseline-slugify | baseline | slugify | completed | completed | - | yes | 19.2 | 202 | 47,073 | - |
| ab-002/run-018-jev-slugify | jev | slugify | completed | completed | jev | yes | 19.1 | 198 | 43,167 | test_evidence |
| ab-002/run-019-jev-durations | jev | durations | completed | completed | jev | yes | 19.1 | 202 | 45,684 | - |
| ab-002/run-020-baseline-durations | baseline | durations | completed | completed | - | yes | 23.0 | 237 | 59,910 | - |
| ab-002/run-021-baseline-legacy-work-options | baseline | legacy-work-options | completed | completed | - | no | 23.5 | 258 | 67,145 | - |
| ab-002/run-022-jev-legacy-work-options | jev | legacy-work-options | completed | completed | jev | yes | 22.9 | 268 | 65,733 | test_evidence |
| ab-002/run-023-jev-schema-roots | jev | schema-roots | completed | completed | jev | no | 25.5 | 267 | 66,359 | test_evidence |
| ab-002/run-024-baseline-schema-roots | baseline | schema-roots | completed | completed | - | no | 27.3 | 297 | 86,396 | - |
| ab-002/run-025-jev-slugify | jev | slugify | completed | completed | jev | yes | 18.6 | 195 | 47,082 | test_evidence |
| ab-002/run-026-baseline-slugify | baseline | slugify | completed | completed | - | yes | 21.0 | 219 | 54,734 | - |
| ab-002/run-027-baseline-durations | baseline | durations | completed | completed | - | yes | 19.2 | 204 | 54,487 | - |
| ab-002/run-028-jev-durations | jev | durations | completed | completed | jev | yes | 21.9 | 220 | 52,894 | test_evidence |
| ab-002-rerun/run-001-baseline-schema-roots | baseline | schema-roots | completed | completed | - | no | 29.6 | 300 | 84,176 | - |
| ab-002-rerun/run-002-jev-schema-roots | jev | schema-roots | completed | completed | jev | no | 20.1 | 186 | 46,575 | test_evidence |
| ab-002-rerun/run-003-jev-legacy-work-options | jev | legacy-work-options | completed | completed | jev | no | 22.7 | 247 | 66,037 | test_evidence |
| ab-002-rerun/run-004-baseline-legacy-work-options | baseline | legacy-work-options | completed | completed | - | no | 29.1 | 311 | 82,673 | - |

## Means by workload and arm

| Workload | Arm | Runs | Hidden pass | Minutes | Requests | Input+cache tokens | Output tokens |
| --- | --- | --- | --- | --- | --- | --- | --- |
| durations | baseline | 4 | 4/4 | 20.9 | 219.8 | 16,816,249 | 56,630 |
| durations | jev | 4 | 4/4 | 16.1 | 163.8 | 12,228,656 | 37,050 |
| legacy-work-options | baseline | 4 | 0/4 | 26.1 | 292.0 | 23,434,995 | 76,610 |
| legacy-work-options | jev | 4 | 2/4 | 21.3 | 235.2 | 18,722,479 | 59,493 |
| schema-roots | baseline | 4 | 1/4 | 28.8 | 331.0 | 26,866,955 | 88,806 |
| schema-roots | jev | 4 | 1/4 | 20.6 | 203.2 | 16,081,400 | 51,686 |
| slugify | baseline | 4 | 4/4 | 20.2 | 207.2 | 15,507,161 | 49,919 |
| slugify | jev | 4 | 4/4 | 18.1 | 175.8 | 13,234,162 | 39,508 |

## Mean requests and output tokens per stage, backlog workloads

| Stage | baseline requests | baseline output | jev requests | jev output |
| --- | --- | --- | --- | --- |
| prepare | 8.9 | 1,876 | 9.5 | 2,227 |
| requirements | 23.8 | 6,577 | 21.1 | 6,266 |
| plan | 15.8 | 5,174 | 4.4 | 1,587 |
| plan-review | 8.5 | 1,646 | 3.2 | 570 |
| decompose | 20.4 | 6,009 | 21.6 | 5,625 |
| implement | 122.2 | 29,673 | 80.6 | 19,659 |
| summarize | 16.6 | 6,340 | 16.0 | 5,018 |
| review | 88.0 | 24,256 | 61.5 | 14,525 |
| publish | 4.9 | 861 | 0.0 | 0 |
| helpers | 2.5 | 296 | 1.2 | 112 |
| total | 311.5 | 82,708 | 219.2 | 55,589 |

## Mean requests and output tokens per stage, planted workloads

| Stage | baseline requests | baseline output | jev requests | jev output |
| --- | --- | --- | --- | --- |
| prepare | 9.5 | 1,914 | 9.8 | 2,270 |
| requirements | 16.5 | 3,965 | 12.0 | 2,745 |
| plan | 13.6 | 3,640 | 11.5 | 2,789 |
| plan-review | 6.9 | 1,159 | 4.6 | 840 |
| decompose | 18.8 | 4,098 | 10.9 | 2,557 |
| implement | 46.4 | 9,718 | 49.6 | 10,006 |
| summarize | 15.6 | 5,102 | 10.5 | 3,154 |
| review | 79.6 | 22,582 | 58.8 | 13,707 |
| publish | 4.1 | 808 | 0.0 | 0 |
| helpers | 2.5 | 289 | 2.1 | 211 |
| total | 213.5 | 53,275 | 169.8 | 38,279 |

## Jev decisions, all runs

Act means Jev decided alone; confirm and escalate left the call to Claude or the full path. Right and wrong count labeled act decisions checked against a lane verdict or the finished diff.

| Decision | Act | Confirm | Escalate | Labeled | Jev right | Jev wrong | Misses |
| --- | --- | --- | --- | --- | --- | --- | --- |
| intake.compact | 6 | 0 | 0 | 6 | 5 | 1 | 1 |
| intake.direct | 10 | 0 | 0 | 10 | 10 | 0 | 0 |
| review.criterion | 25 | 69 | 0 | 76 | 7 | 0 | 0 |
| review.test_evidence | 17 | 0 | 0 | 3 | 3 | 0 | 0 |
| smell.clean | 10 | 2 | 5 | 11 | 4 | 0 | 0 |
