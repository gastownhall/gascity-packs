# Build artifact hash validation

The shared validator requires exactly 64 hexadecimal digits in every `sha256:` trace hash, accepting digest letters in either case.

The producer-stage `build-artifact-valid.sh` gate also verifies file bytes. For standalone validation, enable `--verify-absolute-upstreams` (Python: `verify_absolute_upstreams=True`); leave it off for structure and hash syntax checks alone.

| Trace input | Validation |
| --- | --- |
| Absolute SHA256 path | Current bytes of the named file |
| Relative SHA256 path | Exactly one file beside the artifact or under repeatable `--upstream-root` arguments; equivalent resolved paths count once |
| Missing file or ambiguous relative path | Failure naming the input and roots |
| Relative symlink escaping its root | Failure naming the input and root |
| `git:<revision>` or `bead:<id>` | Historical revision reference, preserved without filesystem comparison |

The gate supplies the durable rig or store root from its runtime environment, or the root used to resolve the artifact when only `GC_WORK_DIR` is available. The check process's working directory isn't an implicit upstream root.

Failures name the trace entry and file, with recorded and actual digests on mismatches. Reconcile a changed input before regenerating its downstream artifact and trace; the existing bounded producer repair loop receives these errors as repair context.

```sh
python3 gascity/assets/scripts/validate_build_artifact.py \
  --schema gc.build.review.v1 --path /workspace/plans/review-report.md \
  --verify-absolute-upstreams --upstream-root /workspace
```
