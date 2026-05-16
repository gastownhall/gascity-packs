# Artifact Signing and Provenance

### Sigstore Cosign Keyless Signing

Sign all published artifacts using **Sigstore Cosign keyless signing**. Keyless signing uses OIDC identity from the CI platform to obtain short-lived signing certificates from Fulcio, **eliminating long-lived signing keys**. Signatures are recorded in the Rekor transparency log for public auditability.

### Sign by Digest

Sign container images by digest, **not by tag**. Tags are mutable. Signing by digest (`sha256:abc123...`) binds the signature to the immutable image content.

### Verify Before Deploy

The deployment pipeline or admission controller (Kubernetes admission webhook, Kyverno, OPA Gatekeeper) validates that the artifact's signature matches the expected signing identity and was recorded in the transparency log. **Unsigned or unverified artifacts must not deploy to staging or production.**

### SLSA Provenance

Generate SLSA provenance attestations during the build. Provenance records:
- Build platform
- Source repository
- Commit SHA
- Build command
- Builder identity

Use SLSA GitHub Generator, GitLab's built-in SLSA, or `slsa-framework/slsa-verifier`.

### SLSA Build Levels

| Level | Requirements |
|:------|:-------------|
| 2 (minimum target) | Builds run on a hosted platform (not developer workstations); provenance is signed by the build service |
| 3 | Adds build isolation (ephemeral, single-tenant build environments) and non-falsifiable provenance |

### SBOM Attestations

Attach SBOMs as signed attestations alongside the artifact: `cosign attest` produces signed in-toto attestations binding the SBOM to the artifact digest. Consumers verify both the artifact signature and the SBOM attestation.

---
[Back to Overview](./OVERVIEW.md)
