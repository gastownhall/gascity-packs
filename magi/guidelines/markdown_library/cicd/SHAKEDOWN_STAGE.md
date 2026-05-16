# Pipeline Shakedown Stage

### Definition

Pipeline shakedown is a **dedicated stage** inserted between build and full-test. It runs the freshly built artifact inside a controlled throwaway environment using a minimal known-good input set, asserts exit code, asserts structural output, and asserts observability emission.

Shakedown answers a single question: **does the artifact that just came out of the build stage actually run end-to-end against its real dependencies under controlled conditions?**

It is **not** a unit test stage, **not** an integration test stage, **not** a load test stage, and **not** a full behavioral regression suite.

### Stage Placement

The shakedown stage lives in pipeline YAML between build and full-test:
- Dedicated job with its own runner
- Own timeout (default 10 minutes)
- Own cleanup guarantees
- Required status check on protected branches

It is **not** a step inside the build job. It is a first-class pipeline stage.

### Preflight vs Shakedown vs Testing

| Stage | Validates |
|:------|:----------|
| **Preflight** | Pipeline environment before build starts: runner has required tools, secrets reachable, registry logged in, checkout succeeded |
| **Shakedown** | The built artifact actually runs against real downstream dependencies with a known-good minimal input set |
| **Testing** | Behavior, performance, correctness, edge cases at scale |

A passing build is not a passing shakedown. A passing shakedown is not a passing test suite.

### Mandatory Triggers

Shakedown is mandatory after:
- Pipeline YAML change
- Runner image or runner pool change
- Base image upgrade
- Language runtime upgrade
- Package manager upgrade
- Direct dependency upgrade with breaking-potential semver movement
- SDK upgrade for any downstream service
- OIDC or secrets injection mechanism change
- Registry or artifact storage change
- Deployment target change
- Rollback mechanism change

### Non-Triggers

- Documentation-only PRs
- README changes
- Comment-only changes to pipeline YAML
- CODEOWNERS updates
- Label-only changes

**Any change to the build graph, dependency graph, runner environment, or deployment path requires shakedown regardless of how small the diff appears.**

### Throwaway Environment

The shakedown environment is a clean, throwaway instance provisioned fresh for the stage and destroyed at stage exit:
- Short-lived container
- Per-PR Kubernetes namespace
- Sandbox cloud subscription
- Canary data plane

Seeded with known-good inputs and pointed at **real** downstream services (sandbox tenants, staging databases, test queues, test billing accounts). **Mocks and stubs defeat the purpose.** The shakedown environment is representative of production, not a replica of it.

### Run the Production Artifact

Shakedown executes the build artifact **exactly as it will run in production**:
- Containers — pull the just-pushed image by digest and run it
- Binaries — download the signed artifact from the registry and invoke it
- Serverless functions — deploy the artifact to the sandbox function runtime and invoke it via its real trigger

**Shakedown never rebuilds the artifact and never substitutes a locally compiled copy.**

### Required Assertions (in order)

1. The artifact starts successfully in the clean environment and reports ready within its documented startup window.
2. Secrets injected via OIDC token exchange or secret store actually reach the artifact and decrypt correctly.
3. The artifact's service account token authenticates to every declared downstream.
4. The happy-path end-to-end flow completes with known-good inputs and produces structurally valid outputs at the declared destination.
5. Emitted logs, metrics, and traces land in the expected observability backend with the expected labels.
6. The artifact exits cleanly on shutdown signal without orphaning resources.

### Release Tagging and Rollback Validation

For release pipelines, shakedown also asserts:
- Artifact tagged with the correct semantic version and commit SHA
- Rollback trigger (manual or automated) is exercised against a canary namespace and successfully reverts to the prior known-good artifact
- Rollback completes within the declared recovery time objective

**A rollback path that has never been exercised under pipeline control is a pipeline defect.**

### Known-Good Input Fixtures

Shakedown inputs are a small, fixed, version-controlled set living under `shakedown/fixtures/` or equivalent. **They are not generated on the fly, not pulled from production snapshots, and not synthesized per run.** Expected outputs are committed alongside inputs. Shakedown diffs actual output against expected output and classifies any mismatch.

### Happy Path Only

Shakedown runs the **happy path only**. No adversarial inputs, no chaos injection, no large-volume load, no fuzzing. Those belong in testing. **A shakedown with a hundred assertions is a misconfigured test suite.**

### Required Artifacts (Per Run)

- Shakedown stage log (full stdout/stderr of the artifact)
- Input fixture manifest
- Output capture
- Diff against expected output
- Resolved artifact digest
- Environment snapshot (runner image digest, downstream service versions, secret store path, OIDC subject)
- Result classification

Artifacts upload to the pipeline's artifact store and are retained for the same window as build artifacts.

### Result Classification

| Outcome | Meaning |
|:--------|:--------|
| **pass** | Every assertion returned the expected result. Full-test stage unblocked. |
| **fail-blocking** | Artifact failed to start, secrets did not inject, downstream auth failed, output diverged from expected, or observability emission missing. **Halt pipeline before full-test.** |
| **fail-nonblocking** | Non-critical log field missing, metric label drifted, or trace span delayed beyond declared window. **Open tracked issue and proceed with full-test.** |
| **inconclusive** | Sandbox downstream unreachable due to a condition outside the artifact. Re-run the specific assertion with the environment condition corrected. |

### Hard Timeout

Default ceiling: **10 minutes**. A shakedown that needs more than 10 minutes is a misconfigured test suite or a startup-latency problem. Neither is acceptable.

### No Optimization During Shakedown

Performance anomalies observed during the stage are recorded as non-blocking issues and carried to the testing stage for investigation. **Tuning runner specs, resource limits, or runtime flags to make shakedown pass is prohibited** — it masks defects that will resurface in production.

### Anti-Patterns (Forbidden)

- Treating unit tests as shakedown
- Running shakedown against fully mocked downstreams
- Running shakedown on a different artifact than the one the build stage produced
- Skipping shakedown on "small" pipeline YAML changes
- Reusing shakedown results from a prior pipeline run
- Discarding shakedown artifacts at stage exit
- Gating shakedown on manual approval (shakedown is automated and executes on every qualifying run)

### Reference: GitHub Actions Stage

```yaml
# .github/workflows/release.yml — shakedown stage between build and full-test
jobs:
  build:
    runs-on: ubuntu-24.04
    outputs:
      image-digest: ${{ steps.push.outputs.digest }}
    steps:
      - uses: actions/checkout@b4ffde65f46336ab88eb53be808477a3936bae11
      - id: push
        run: |
          docker build --tag "${IMAGE}:${GITHUB_SHA}" .
          docker push "${IMAGE}:${GITHUB_SHA}"
          echo "digest=$(docker inspect --format='{{index .RepoDigests 0}}' "${IMAGE}:${GITHUB_SHA}")" >> "${GITHUB_OUTPUT}"

  shakedown:
    needs: build
    runs-on: ubuntu-24.04
    timeout-minutes: 10
    permissions:
      id-token: write
      contents: read
    environment: shakedown-sandbox
    steps:
      - uses: actions/checkout@b4ffde65f46336ab88eb53be808477a3936bae11
      - name: OIDC token exchange to sandbox cloud
        uses: azure/login@a65d910e8af852a8061c627c456678ba44b8a7ec
        with:
          client-id: ${{ secrets.SANDBOX_CLIENT_ID }}
          tenant-id: ${{ secrets.SANDBOX_TENANT_ID }}
          subscription-id: ${{ secrets.SANDBOX_SUBSCRIPTION_ID }}
      - name: Pull artifact by digest (no rebuild)
        run: docker pull "${{ needs.build.outputs.image-digest }}"
      - name: Run artifact in clean throwaway container
        run: |
          docker run --rm --name shakedown \
            --env-file shakedown/fixtures/env.sandbox \
            -v "${PWD}/shakedown/fixtures:/fixtures:ro" \
            -v "${PWD}/.shakedown/out:/out" \
            "${{ needs.build.outputs.image-digest }}" \
            --input /fixtures/known-good.json \
            --output /out/actual.json
      - name: Diff actual output against expected
        run: diff -u shakedown/fixtures/expected.json .shakedown/out/actual.json
      - name: Confirm observability emission
        run: ./shakedown/bin/assert-logs-landed.sh "${{ needs.build.outputs.image-digest }}"
      - name: Exercise rollback against canary namespace
        run: ./shakedown/bin/exercise-rollback.sh "${{ needs.build.outputs.image-digest }}"
      - name: Upload shakedown artifacts
        if: always()
        uses: actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02
        with:
          name: shakedown-${{ github.run_id }}
          path: |
            .shakedown/out/
            .shakedown/env-snapshot.json
          retention-days: 30

  full-test:
    needs: shakedown
    runs-on: ubuntu-24.04
    steps:
      - run: ./ci/full-regression.sh
```

---
[Back to Overview](./OVERVIEW.md)
