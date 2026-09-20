# Duplicate investigation order

No duplicate verdict is supplied. Investigate candidates before applying the existing triage policy.

## Source issue
Package signature verification skipped
Installer accepts an archive with an invalid signature, contrary to the required verification policy.

## Candidate 1: C1
Bad signature accepted by installer
An archive signed with the wrong key still installs; signature verification is required.

## Candidate 2: C2
Signing release artifacts
Add a new signing step to the release pipeline.

## Candidate 3: C3
Checksum network timeout
Checksum download times out during an outage.
