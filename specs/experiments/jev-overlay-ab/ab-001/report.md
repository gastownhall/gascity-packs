# Jev build A/B report

## Runs

| Run | Arm | Workload | Build | Harness status | Review gate | Hidden pass | Minutes | Requests | Output tokens | Skipped lanes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| run-001-baseline-slugify | baseline | slugify | completed | completed | - | yes | 19.4 | 254 | 78,008 | - |
| run-002-jev-slugify | jev | slugify | completed | completed | jev | yes | 18.6 | 226 | 70,609 | test_evidence |
| run-003-jev-durations | jev | durations | completed | completed | jev | yes | 18.9 | 238 | 84,213 | test_evidence |
| run-004-baseline-durations | baseline | durations | completed | completed | - | yes | 21.2 | 287 | 93,401 | - |
| run-005-baseline-legacy-work-options | baseline | legacy-work-options | completed | completed | - | yes | 30.3 | 442 | 145,269 | - |
| run-006-jev-legacy-work-options | jev | legacy-work-options | completed | failed | escalate:receipts | no | 23.2 | 417 | 131,068 | - |
| run-007-jev-schema-roots | jev | schema-roots | completed | failed | escalate:receipts | no | 35.9 | 498 | 177,937 | - |
| run-008-baseline-schema-roots | baseline | schema-roots | completed | completed | - | no | 31.6 | 450 | 154,675 | - |
| run-009-jev-slugify | jev | slugify | completed | completed | jev | yes | 17.1 | 212 | 62,201 | test_evidence |
| run-010-baseline-slugify | baseline | slugify | completed | completed | - | yes | 18.4 | 262 | 81,829 | - |
| run-011-baseline-durations | baseline | durations | completed | completed | - | yes | 23.3 | 329 | 105,179 | - |
| run-012-jev-durations | jev | durations | completed | completed | jev | yes | 19.9 | 259 | 84,130 | test_evidence |
| run-013-jev-legacy-work-options | jev | legacy-work-options | completed | failed | escalate:receipts | no | 24.7 | 384 | 123,636 | - |
| run-014-baseline-legacy-work-options | baseline | legacy-work-options | completed | completed | - | yes | 25.5 | 396 | 124,503 | - |
| run-015-baseline-schema-roots | baseline | schema-roots | completed | completed | - | no | 28.8 | 347 | 124,602 | - |
| run-016-jev-schema-roots | jev | schema-roots | completed | failed | escalate:receipts | no | 26.5 | 330 | 111,957 | - |

## Means by workload and arm

| Workload | Arm | Runs | Hidden pass | Minutes | Requests | Input+cache tokens | Output tokens |
| --- | --- | --- | --- | --- | --- | --- | --- |
| durations | baseline | 2 | 2/2 | 22.2 | 308.0 | 24,552,020 | 99,290 |
| durations | jev | 2 | 2/2 | 19.4 | 248.5 | 19,612,246 | 84,172 |
| legacy-work-options | baseline | 2 | 2/2 | 27.9 | 419.0 | 33,668,078 | 134,886 |
| legacy-work-options | jev | 2 | 0/2 | 23.9 | 400.5 | 33,106,063 | 127,352 |
| schema-roots | baseline | 2 | 0/2 | 30.2 | 398.5 | 31,546,340 | 139,638 |
| schema-roots | jev | 2 | 0/2 | 31.2 | 414.0 | 33,966,143 | 144,947 |
| slugify | baseline | 2 | 2/2 | 18.9 | 258.0 | 20,118,392 | 79,918 |
| slugify | jev | 2 | 2/2 | 17.9 | 219.0 | 16,881,902 | 66,405 |

## Mean requests and output tokens per stage, backlog workloads

| Stage | baseline requests | baseline output | jev requests | jev output |
| --- | --- | --- | --- | --- |
| prepare | 9.2 | 1,687 | 8.5 | 2,028 |
| requirements | 23.5 | 6,465 | 21.0 | 7,059 |
| plan | 15.0 | 5,446 | 16.8 | 5,325 |
| plan-review | 6.5 | 1,014 | 7.0 | 946 |
| decompose | 19.8 | 5,646 | 18.2 | 5,331 |
| implement | 137.0 | 33,370 | 153.0 | 40,021 |
| summarize | 24.2 | 9,448 | 20.8 | 7,646 |
| review | 82.0 | 21,409 | 69.2 | 17,505 |
| publish | 6.2 | 1,086 | 0.0 | 0 |
| helpers | 85.2 | 51,692 | 92.8 | 50,290 |
| total | 408.8 | 137,262 | 407.2 | 136,150 |

## Mean requests and output tokens per stage, planted workloads

| Stage | baseline requests | baseline output | jev requests | jev output |
| --- | --- | --- | --- | --- |
| prepare | 9.0 | 1,726 | 9.0 | 2,174 |
| requirements | 17.0 | 4,276 | 17.2 | 4,509 |
| plan | 16.8 | 4,190 | 12.5 | 3,634 |
| plan-review | 6.2 | 1,051 | 7.2 | 1,111 |
| decompose | 19.5 | 4,440 | 16.8 | 3,894 |
| implement | 44.8 | 9,378 | 47.5 | 10,056 |
| summarize | 18.2 | 5,394 | 14.0 | 4,028 |
| review | 79.0 | 22,205 | 54.2 | 12,612 |
| publish | 4.8 | 759 | 0.0 | 0 |
| helpers | 67.8 | 36,184 | 55.2 | 33,270 |
| total | 283.0 | 89,604 | 233.8 | 75,288 |
