Prepare the build-basic starter factory review.

Read the canonical absolute artifact root from root metadata
`gc.build.artifact_root` and require it to be a real directory. Gather the
requirements, plan, decomposition, canonical implementation summary, task
evidence, changed files, and proof commands into exactly
`<artifact-root>/review-context.md`. Record that canonical absolute path as
`gc.build.code_review_context_path`. The context and canonical summary must be
distinct regular non-symlink files directly under that same root.

The implementation source of truth is the closed source anchor/worktree recorded
by the implementation summary and task evidence. Include the source anchor id,
its `work_dir`, changed files, commit id, and proof commands in the context. The
launcher rig root may remain unchanged until an explicit publish step; do not
present an unchanged root checkout as a review failure when the source
anchor/worktree contains the verified implementation.

Resolve every exact implementation-convoy member and its current full recorded
commit before writing the context. Compute the implementation snapshot as the
`sha256` digest of compact JSON containing each member id and commit, sorted by
member id with object keys sorted and no trailing newline. Record the result on
the workflow root as
`gc.build.implementation_snapshot=sha256:<64-lowercase-hex-digits>` and include
the exact tuple list and snapshot in the review context. Fail closed if a member
commit does not resolve in its authoritative worktree. This value binds every
review lane to the same implementation bytes.

Canonicalize every commit to its lowercase full SHA before serialization. A
one-member payload is exactly
`[{"commit":"<canonical lowercase full SHA>","id":"<id>"}]`: sort members by
id, sort every object key, use compact JSON separators, and hash those bytes
with no trailing newline.

After the context is complete, bind the exact review inputs. Compute current
`sha256:<digest>` values from the raw summary and context bytes. Serialize this
exact compact, sorted-key JSON with canonical absolute paths and no newline:
`{"context":{"path":"<context>","sha256":"sha256:<digest>"},"implementation_snapshot":"sha256:<digest>","summary":{"path":"<summary>","sha256":"sha256:<digest>"}}`.
Hash those UTF-8 bytes and record the result on the workflow root as
`gc.build.review_input_snapshot=sha256:<digest>`. Do not place that combined
digest inside the context itself (that creates a self-hash cycle).

Do not trust a model-computed digest. After the draft context and root paths
exist, run the installed helper from the launcher Git root:
`python3 "<launcher-root>/.gc/scripts/verify_implementation_provenance.py" --emit-current --root-id "<workflow-root-id>" --expected-summary "<canonical-summary>" --validator "<launcher-root>/.gc/scripts/validate_build_artifact.py"`.
Use its exact sorted `members` and `implementation_snapshot` in the context,
rewrite the context once, then run the command again. Publish only that second
`implementation_snapshot` and `review_input_snapshot`. Read the root back and
rerun the helper without `--emit-current`, adding
`--expected-snapshot <implementation_snapshot>`; any failure blocks closure.

This starter factory intentionally uses only three review lanes so new users can
see fanout/fanin without a large reviewer roster.

Do not invoke provider-native subagents. Gas City graph lanes are the
delegation mechanism.

Close with `gc.outcome=pass` only after the context path, implementation
snapshot, and review-input snapshot are recorded.
