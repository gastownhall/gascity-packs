{{ define "magi-usage" }}
Use `gc magi <verb>` when:
- you need to install, update, or remove a model-runtime (Claude, Codex, Gemini, OpenAI/LM Studio) — use `install` or `uninstall`.
- you need a structural overview of a project or a follow-on improvement backlog — use `analyze` then `improve`.
- you need to verify every magi precondition before a deploy — use `doctor`.
- you need to inspect what magi has installed plus open bd work — use `status` or `ready`.
- you need to chain doctor → install → bootstrap-project → status → analyze as one molecule — use `molecule bootstrap` or `formulas cook mol-magi-bootstrap`.
- you need a portable `.utilities/` symlink wired into a project — use `bootstrap-project`.
- you need to persist a magi-namespaced design note via bd — use `remember` or `recall`.

Do not use it for:
- ad-hoc rsync against the vendored `claude/`, `codex/`, `gemini/`, or `openai/` directories.
- direct edits to those vendored trees — every change vanishes on next re-vendor.
- shelling out to `<target>/deploy_harness.sh` directly — the orchestrator handles env passthrough, redaction, idempotency, and bd lifecycle.
- passing secrets in `--context` payloads to `analyze` or `improve` — those payloads land in LM Studio logs.

When you use it:
1. Run `gc magi doctor` before any install. Exit 0 or 2 permits proceeding; exit 1 stops the chain.
2. Pass absolute paths to `analyze`, `improve`, and `bootstrap-project`. Relative paths fail at parse time.
3. Treat the bd bead id as the authoritative run handle. The bead id appears in `state.json` and in the verb log header.
4. Re-runs within `IDEMPOTENT_WINDOW_SECONDS=300` reuse the prior bead when the flag fingerprint matches and the prior bead closed `outcome:0`.
5. Never include secrets in `--context` or in `remember` values. Redaction is defense-in-depth; the source of truth is the env file the secret came from.
6. bd absent does not block any verb. Status degrades to `state.json` only; install/analyze/improve still run.
{{ end }}
