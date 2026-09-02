# ADR Review Manifest

- Status: completed
- Review date: 2026-09-02

## Review Summary

Durable decision is that N-model fanout belongs in a city provider panel
owned by Gas City, not in pack Task spawn and not in a `graph_operator`
interpreter. Pack docs record that decision. Formula stamps wait for a
consumer.

## In-Force ADRs Reviewed

- None. `gascity-packs` has no `adr/` tree. Dest-env `adr/0027-pstack-gascity-pack.md` remains the pack mapping ADR and is not superseded here.

## New Durable ADRs Created

- None in `gascity-packs/adr/`. Dest-env should add an ADR for
  `[[provider_panels]]` when the compiler change lands.
