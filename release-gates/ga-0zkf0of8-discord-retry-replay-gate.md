# Release gate: Discord retry/replay and supervisor endpoint

**Verdict:** **PASS**

- Evaluated: 2026-11-05T20:40:23.966728+00:00
- Deploy bead: `ga-0zkf0of8`; build: `ga-6y1i5p`; review: `ga-0cwz0ul`.
- Repository: `gastownhall/gascity-packs`; deploy mode: `remote`; base ref: `origin/main`.
- Reviewed source: `4d67c8e46e2ecbdcdb4e096fb1d3da3872b3834b` (resolved as a commit; never taken from a branch tip).
- Pinned base: `796d7ecd73cf36792e5aa8ec771bcc33ee68cd00`.
- Gated synthetic merge: `345b18c1fc6813e5c5c1f2e1e5dd32aaa884f421`; tree: `e2ed3c998f42cafde2801a74e578198e66e5bdff`.
- `merge_state: clean (origin/main@796d7ecd73cf)`.
- `gate_base_kind: current-tip`; `merge_validation: MPR revalidates the merge result at merge time`.
- Preflight: source commit/pulls has no PR; checked again after CI. No existing deploy branch or gate commit for this bead.
- Source branch `builder/ga-6y1i5p` is provenance only. Publication branch is mechanically derived as `deploy/ga-0zkf0of8-gate` from the reviewed source.

| # | Result | Evidence |
|---|---|---|
| 1 Review PASS | PASS | Closed review `ga-0cwz0ul` records PASS for the resolved source above. No carryover or reviewer-added commit changes this source. |
| 2 Acceptance | PASS | Retry/replay port and supervisor configuration checked against code and real test results below. The deployment-only requirement to open a PR is performed after this gate and must be verified on the deploy bead before close/report; this record does not claim a PR already exists. |
| 3 Full required CI scope | PASS | Original full Python invocation plus the previously unexecuted CI remainder cover every required command in `.github/workflows/ci.yml`. Original Python: 1,862 PASS / 1 attributed non-owned FAIL / 11 SKIP plus 9,993 passing subtests. CI-release Python groups: 38 PASS / 0 FAIL / 9 SKIP plus 2 passing subtests. Go: 1,061 PASS / 0 FAIL / 0 test SKIP. All 16 shell scripts and all 11 pack lint commands exit 0. All 28 owned tests PASS by name. |
| 4 Open HIGH findings | PASS | Zero blocking/HIGH findings in the live closed review. Minor logging, retry duration, and retained-envelope observations remain documented there. |
| 5 Clean branch | PASS | Gated source checkout is clean after all checks. This gate record is the only publication addition; push is blocked unless the isolated deploy branch is clean after committing it. |
| 6 Merge/build state | PASS | Source merged cleanly with the pinned current base. All five changed Python files compile under warnings-as-errors and Python 3.12 AST grammar; full tests run on that exact merge tree. No source rebase or conflict resolution. |
| 7 Single feature | PASS | All five changed files are under `discord/`, implementing the same ingress recovery/endpoint behavior. Three source commits cite accepted feature IDs `ga-6y1i5p` and validator `ga-ufu4c`; no unrelated source or internal-doc paths ride the ancestry. |

## Acceptance evidence

- Port preserves current ingress locking and idempotency behavior. ECONNREFUSED retries use delays 2, 4, 8, 16, 32 seconds (62 total); other HTTP/timeout/error classes do not take this retry path. Buffered replay reuses the original idempotency key and reloads under the ingress lock. Ambiguous and terminal outcomes discard the buffer; pending delivery retains existing recovery semantics. Buffered message text is redacted.
- `GC_SUPERVISOR_API_BASE_URL` is read per call, stripped, and defaults to `http://127.0.0.1:8372` when blank. `GC_API_BASE_URL` retains its city-scoped meaning. New configuration/fallback tests PASS.
- The four baseline methods explicitly asserting 8372 PASS: `test_gc_api_base_url_prefers_supervisor_api_when_available`, `test_gc_api_base_url_uses_site_workspace_name_when_city_toml_omits_name`, `test_gc_api_base_url_falls_back_to_city_dir_basename_when_no_declared_name`, and `test_gc_api_request_routes_through_supervisor_city_scope`. The build request says five existing tests; four literal methods exist at base, all existing Discord tests pass, and the new blank-override default test also PASSes. No fifth test was invented.
- `test_peer_root_budget_index_tracks_root_counts` PASSes in this gate's empty environment. It is not a failure of this change on this base.
- Python runs use `env -i`, an isolated HOME, and `PYTHONUSERBASE=/home/jaword/.local`; no live `GC_CITY_ROOT` reaches tests. The live checkout and Discord services were not modified or restarted. Every gate command ran in a private checkout.
- Host Python is 3.14.8; CI specifies 3.12.16. The five changed files also parse under the 3.12 grammar; PR CI remains the Python 3.12 execution.

## Command and scope accounting

`test_cmd_scope: full-suite`

Fast lane ran first, in fresh isolated views: changed Python compile/AST checks, `git diff --check`, and `python3 validate_registry.py --require-git` (registry OK), retained under `/var/tmp/gc-heavy-gate/runs/ga-0zkf0of8.fast`. Target repository configures no Python format/lint or generated-file drift command. No Bazel configuration exists in this cross-repo target; the native commands below are its documented CI commands.

- Original complete-CI script: `/var/tmp/gc-heavy-gate/runs/ga-0zkf0of8.c3/suite.sh`. The first command runs all ten Python roots listed in CI, with `-q -rA --junitxml=...` and explicit real dev `GC_TEST_BIN` to avoid `/usr/bin/gc` (Graphviz). Full output/JUnit retained as `/var/tmp/gc-heavy-gate/runs/ga-0zkf0of8.c3/python.log` and `/var/tmp/gc-heavy-gate/runs/ga-0zkf0of8.c3/python.xml`.
- The original script stopped after its single unrelated failure. After applying the attribution protocol, `/var/tmp/gc-heavy-gate/runs/ga-0zkf0of8.ci-remainder/suite.sh` runs only the previously unexecuted required CI commands, in their original order. It does not rerun the full Python suite or replace its failure with a later green result.
- CI-required release install resolves to `gc 1.5.1` / Go 1.26.10 in a private GOBIN. The mandated later composition invocation passes with this separate release binary; the earlier dev-binary failure stays in the counts.
- All six Go modules run `go test -json -v ./...`; runtime-cloudflare also runs `go vet ./...`. JSON `Output` fields are losslessly decoded into `/var/tmp/gc-heavy-gate/runs/ga-0zkf0of8.ci-remainder/go-evidence-text`, then read with `gate-test-evidence.py`; reader result OK, 1,061 PASS / 0 FAIL / 0 SKIP. Runtime fakeworker emits a package-level `[no test files]`, not a skipped test.
- The only CI step not run is runtime-cloudflare RPP conformance, explicitly non-blocking (`continue-on-error: true`) in the unchanged workflow. Every required step is covered.
- `ci_required_closure: n/a (no ci-required aggregate)`; `ci_lane_run: n/a (no CI-config change)`.
- `test_exec_mode: local`; `test_exec_bep: n/a (non-Bazel target)`; `rbe_state: n/a`; `fallback_reason: n/a`; `heavy_mode: none`; `waiver_ref: none`.
- `test_log_dir: /var/tmp/gc-heavy-gate/runs/ga-0zkf0of8.c3` and `/var/tmp/gc-heavy-gate/runs/ga-0zkf0of8.ci-remainder`; all raw per-step logs and JSON/JUnit are retained, not deleted.

| CI remainder step | Result |
|---|---|
| `gc-install` | PASS (exit 0) |
| `gc-version` | PASS (exit 0) |
| `lint-gascity` | PASS (exit 0) |
| `lint-gascity-roles` | PASS (exit 0) |
| `lint-bmad` | PASS (exit 0) |
| `lint-compound-engineering` | PASS (exit 0) |
| `lint-gstack` | PASS (exit 0) |
| `lint-superpowers` | PASS (exit 0) |
| `lint-profiler` | PASS (exit 0) |
| `lint-pr-pipeline` | PASS (exit 0) |
| `lint-slack-channel` | PASS (exit 0) |
| `lint-slack-full` | PASS (exit 0) |
| `lint-slack-mini` | PASS (exit 0) |
| `order-scopes` | PASS (exit 0) |
| `composition` | PASS (exit 0) |
| `maintained-packs` | PASS (exit 0) |
| `gastown-lint` | PASS (exit 0) |
| `shell-test_deacon_dolt_health_guard` | PASS (exit 0) |
| `shell-test_deacon_ends_turn` | PASS (exit 0) |
| `shell-test_gastown_pack_assets` | PASS (exit 0) |
| `shell-test_gastown_theme_scripts` | PASS (exit 0) |
| `shell-test_mayor_dispatch_failure_rule` | PASS (exit 0) |
| `shell-test_mol_refinery_patrol_rebase_guard` | PASS (exit 0) |
| `shell-test_mol_witness_patrol_orphan_recovery` | PASS (exit 0) |
| `shell-test_patrol_wisp_lifecycle` | PASS (exit 0) |
| `shell-test_polecat_artifact_dir` | PASS (exit 0) |
| `shell-test_polecat_churn_watcher` | PASS (exit 0) |
| `shell-test_polecat_push_gate` | PASS (exit 0) |
| `shell-test_pr_artifact_lifecycle` | PASS (exit 0) |
| `shell-test_pr_merge_reconcile` | PASS (exit 0) |
| `shell-test_review_check_scripts_gc_ready` | PASS (exit 0) |
| `shell-test_witness_heartbeat_check` | PASS (exit 0) |
| `shell-test_worktree_setup_sync` | PASS (exit 0) |
| `go-root` | PASS (exit 0) |
| `go-slack-full-adapter` | PASS (exit 0) |
| `go-slack-full-cli` | PASS (exit 0) |
| `go-slack-channel-adapter` | PASS (exit 0) |
| `go-slack-mini-adapter` | PASS (exit 0) |
| `runtime-vet` | PASS (exit 0) |
| `go-runtime-cloudflare-runtime` | PASS (exit 0) |

| Go module invocation | PASS | FAIL | test SKIP |
|---|---:|---:|---:|
| `go-root` | 3 | 0 | 0 |
| `go-runtime-cloudflare-runtime` | 12 | 0 | 0 |
| `go-slack-channel-adapter` | 97 | 0 | 0 |
| `go-slack-full-adapter` | 710 | 0 | 0 |
| `go-slack-full-cli` | 199 | 0 | 0 |
| `go-slack-mini-adapter` | 40 | 0 | 0 |

## Failure attribution (not a waiver)

`failure_attribution: test_plain_gastown_polecat_sling_starts_default_graph_workflow -> ga-dmt8zoqj | clause 3: a (MECHANISM)`

- Clause 1: test/module is not diff-owned. Its blob at base and gated tree is identical; all changed production/test files are under Discord.
- Clause 2: open title/condition and gate-tracker searches found no covering condition; closed lookup read 84 trackers and returned NONE. A new record-only tracker `ga-dmt8zoqj` was created, opened/read back, and never routed/slung. It was created in this run, not claimed pre-existing. The gm-sf3238 first-sighting exception applies because clauses 1/4 are clear and proof (a) landed.
- Clause 3(a): the failing module imports only stdlib and pytest. No root/tests conftest, package init, pytest plugin, or child process reads changed Discord code. Its child is the unchanged Gastown fixture plus the external installed dev CLI, which refuses generated bead `gsi-1` versus fixture rig prefix `gc`. The test module and entire Gastown tree equal their pinned base objects. The installed dev CLI SHA256 is `2073b0ef6517ccf93cc78fd81daec4c8a86dcc6b6e32600d6280d917d24d47b2`.
- Clause 4: no directory overlap (`tests/` versus `discord/scripts/` and `discord/tests/`). The inconclusive/same-package paths are not used.
- Proof: `/var/tmp/gc-heavy-gate/runs/ga-0zkf0of8.c3/unrelated-prefix-failure-proof.json`. No failure was retried into a PASS, no waiver metadata is set, and the raw failing log remains. This is a first-hit attribution, not a repeated-signature exception.

## Skip inventory

All 11 original Python skips are unchanged and unowned. The nine maintained-pack absence skips recur in their separate CI-release invocation. Verified matching base/gated source objects and rationale are in `/var/tmp/gc-heavy-gate/runs/ga-0zkf0of8.c3/python-skip-inventory.json`. Maintained-pack helpers load only the named unchanged packs, not Discord; root-only Slack ownership checks explicitly require euid 0, while this gate and CI run unprivileged. No diff-owned SKIP or MISSING result exists.

- `tests.test_maintained_packs_live_gc::test_pack_registers_the_command_verbs_it_ships[oversight-rig]` — oversight-rig ships no commands.
- `tests.test_maintained_packs_live_gc::test_pack_formulas_resolve_through_a_city[oversight-rig]` — oversight-rig ships no formulas.
- `tests.test_maintained_packs_live_gc::test_pack_formulas_resolve_through_a_city[slack-channel]` — slack-channel ships no formulas.
- `tests.test_maintained_packs_live_gc::test_pack_formulas_resolve_through_a_city[slack-full]` — slack-full ships no formulas.
- `tests.test_maintained_packs_live_gc::test_pack_formulas_resolve_through_a_city[slack-mini]` — slack-mini ships no formulas.
- `tests.test_maintained_packs_live_gc::test_pack_agents_resolve_through_a_city[pr-pipeline]` — pr-pipeline ships no agents.
- `tests.test_maintained_packs_live_gc::test_pack_agents_resolve_through_a_city[slack-channel]` — slack-channel ships no agents.
- `tests.test_maintained_packs_live_gc::test_pack_agents_resolve_through_a_city[slack-full]` — slack-full ships no agents.
- `tests.test_maintained_packs_live_gc::test_pack_agents_resolve_through_a_city[slack-mini]` — slack-mini ships no agents.
- `slack-full.tests.test_adapter_run_sh::test_home_less_build_refuses_a_build_dir_owned_by_another_user[gocache]` — requires root to create a directory owned by another user.
- `slack-full.tests.test_adapter_run_sh::test_home_less_build_refuses_a_build_dir_owned_by_another_user[gopath]` — requires root to create a directory owned by another user.

## Diff-owned tests executed

The three candidate test files were compared by AST test body. There are 28 additions; the other edit only isolates the new environment variable in existing test setup. Every owned test is found in the full-suite JUnit, with no FAIL/SKIP/error. Evidence: `/var/tmp/gc-heavy-gate/runs/ga-0zkf0of8.c3/owned-tests.json` and `/var/tmp/gc-heavy-gate/runs/ga-0zkf0of8.c3/python-owned-results.json`.

- `discord/tests/test_discord_gateway_service.py::DiscordGatewayServiceTests::test_buffered_target_failed_status_includes_buffered_delivery` — PASS
- `discord/tests/test_discord_gateway_service.py::DiscordGatewayServiceTests::test_buffered_target_pending_status_includes_buffered_delivery` — PASS
- `discord/tests/test_discord_gateway_service.py::DiscordGatewayServiceTests::test_buffered_target_delivered_status_omits_buffered_delivery` — PASS
- `discord/tests/test_discord_gateway_service.py::DiscordGatewayServiceTests::test_buffered_target_normalizes_empty_intent_to_default` — PASS
- `discord/tests/test_discord_gateway_service.py::DiscordGatewayServiceTests::test_buffered_target_stores_error_when_provided` — PASS
- `discord/tests/test_discord_gateway_service.py::DiscordGatewayServiceTests::test_buffered_target_omits_error_when_empty` — PASS
- `discord/tests/test_discord_gateway_service.py::DiscordGatewayServiceTests::test_replay_buffered_ingress_deliveries_redrives_failed_target` — PASS
- `discord/tests/test_discord_gateway_service.py::DiscordGatewayServiceTests::test_replay_buffered_ingress_deliveries_uses_original_idempotency_key` — PASS
- `discord/tests/test_discord_gateway_service.py::DiscordGatewayServiceTests::test_replay_buffered_ingress_deliveries_marks_failed_on_gc_api_error` — PASS
- `discord/tests/test_discord_gateway_service.py::DiscordGatewayServiceTests::test_replay_buffered_ingress_deliveries_logs_failure_to_stderr` — PASS
- `discord/tests/test_discord_gateway_service.py::DiscordGatewayServiceTests::test_replay_buffered_ingress_deliveries_skips_recent_receipts` — PASS
- `discord/tests/test_discord_gateway_service.py::DiscordGatewayServiceTests::test_replay_buffered_ingress_deliveries_skips_receipts_without_buffered_targets` — PASS
- `discord/tests/test_discord_gateway_service.py::DiscordGatewayServiceTests::test_replay_buffered_ingress_deliveries_partial_delivery_yields_partial_failed_status` — PASS
- `discord/tests/test_discord_intake_common.py::DiscordIntakeCommonTests::test_gc_api_base_url_uses_supervisor_base_from_environment` — PASS
- `discord/tests/test_discord_intake_common.py::DiscordIntakeCommonTests::test_gc_api_url_scopes_requests_under_environment_supervisor_base` — PASS
- `discord/tests/test_discord_intake_common.py::DiscordIntakeCommonTests::test_gc_api_base_url_blank_supervisor_base_keeps_default` — PASS
- `discord/tests/test_discord_intake_common.py::DiscordIntakeCommonTests::test_gc_api_base_url_city_scoped_override_beats_supervisor_base` — PASS
- `discord/tests/test_discord_intake_common.py::DiscordIntakeCommonTests::test_gc_api_request_retries_connection_refused_up_to_limit` — PASS
- `discord/tests/test_discord_intake_common.py::DiscordIntakeCommonTests::test_gc_api_request_succeeds_after_connection_refused_retry` — PASS
- `discord/tests/test_discord_intake_common.py::DiscordIntakeCommonTests::test_gc_api_request_does_not_retry_http_errors` — PASS
- `discord/tests/test_discord_intake_common.py::DiscordIntakeCommonTests::test_gc_api_request_does_not_retry_timeout_errors` — PASS
- `discord/tests/test_discord_intake_common.py::DiscordIntakeCommonTests::test_gc_api_request_does_not_retry_non_connection_refused_url_error` — PASS
- `discord/tests/test_discord_intake_common.py::DiscordIntakeCommonTests::test_gc_api_request_logs_retry_attempt_to_stderr` — PASS
- `discord/tests/test_discord_intake_common.py::DiscordIntakeCommonTests::test_gc_api_request_logs_exhaustion_to_stderr` — PASS
- `discord/tests/test_discord_intake_common.py::DiscordIntakeCommonTests::test_gc_api_request_sleeps_with_correct_backoff_delays` — PASS
- `discord/tests/test_discord_intake_common.py::DiscordIntakeCommonTests::test_redact_chat_ingress_record_redacts_buffered_delivery_message` — PASS
- `discord/tests/test_discord_intake_common.py::DiscordIntakeCommonTests::test_redact_chat_ingress_record_leaves_delivered_targets_untouched` — PASS
- `discord/tests/test_discord_intake_common.py::DiscordIntakeCommonTests::test_redact_chat_ingress_record_handles_target_without_buffered_delivery_key` — PASS

## Load, disk and isolation evidence

Both suites run through `load-gate-run.sh --threshold 15 --max-wait 1800 -- isolated-test-run.sh -- env -i ...`, detached as systemd services. The target is not in the wrapper's isolate list, so wrapper mode is PASS-THROUGH; the private checkout plus explicit empty environment supplies isolation, with per-Python-step `env -i` too. No live city path is inherited.

- `full-python`: `LOAD_GATE_SUMMARY threshold=15 waited_seconds=1806 wait_timed_out=1 run_start_load=87.27 run_max_load=84.66 run_mean_load=83.74 run_readings=5 wait_first_load=21.20 wait_max_load=87.27 wait_mean_load=56.18 wait_readings=61 read_errors=0`
- `ci-remainder`: `LOAD_GATE_SUMMARY threshold=15 waited_seconds=1801 wait_timed_out=1 run_start_load=26.39 run_max_load=31.35 run_mean_load=29.26 run_readings=7 wait_first_load=42.68 wait_max_load=42.68 wait_mean_load=26.85 wait_readings=61 read_errors=0`

These lines record `load_threshold`, `load_waited_seconds`, `load_wait_timed_out`, `run_start_load`, `run_max_load`, `run_mean_load`, and `run_readings` without mixing wait/run measurements. Both ordinary bounded waits timed out and proceeded by policy. The release CLI install reported no user bus for the Go shim's slice and proceeded with its documented fallback; load measurements above include it.

The earlier 19:09:15Z attempt was refused before any test at 39.0 GiB free / 40 GiB floor (exit 98), not a failing test result. That refusal and its one verified replacement mayor notification are retained in the bead notes. Disk checks passed before each actual launch; the CI remainder wrapper observed 43.0 GiB free. The refused attempt contributes no tests and no verdict.

Original full-Python run's final exit is 1 (the attributed dev-fixture failure). CI remainder's final result is `status=complete units=1/1 failed=0`, with all 40 expected steps checked against the workflow/glob inventory. Gate PASS is reached from that complete required scope and the documented first-hit attribution, not from the remainder marker alone.
