# Bluewater

**Independent pack repository:** [github.com/boylec/bluewater](https://github.com/boylec/bluewater)

Bluewater is a naval-doctrine multi-agent orchestration pack —
opinionated alternative to gastown with CO/XO/OOD command continuity,
formal watch turnover, pre-composed casualty response, and
cross-provider two-key launches.

It lives in its own repository (it's large enough to deserve one — 175
files, ~8200 lines including six required departments inline plus three
optional sub-packs for flight-deck choreography, Discord, and Slack
intake). This entry exists in `gascity-packs` as a discovery pointer,
not as a vendored copy.

## Install

```bash
gc pack add github.com/boylec/bluewater
```

## Optional sub-packs

```bash
gc pack add github.com/boylec/bluewater/packs/bluewater-air      # carrier-class production deploys
gc pack add github.com/boylec/bluewater/packs/bluewater-discord  # Discord intake
gc pack add github.com/boylec/bluewater/packs/bluewater-slack    # Slack intake
```

## Documentation

All docs live in the bluewater repo:

- [`README.md`](https://github.com/boylec/bluewater/blob/main/README.md) — overview + department table
- [`docs/install.mdx`](https://github.com/boylec/bluewater/blob/main/docs/install.mdx) — install walkthrough + provider/model tier table
- [`docs/quickstart.mdx`](https://github.com/boylec/bluewater/blob/main/docs/quickstart.mdx) — six steps to a running smoke-test convoy
- [`docs/use_cases.mdx`](https://github.com/boylec/bluewater/blob/main/docs/use_cases.mdx) — what to do when, with verification
- [`docs/first_watch.mdx`](https://github.com/boylec/bluewater/blob/main/docs/first_watch.mdx) — narrative walkthrough of one OOD watch
- [`doctrine/`](https://github.com/boylec/bluewater/tree/main/doctrine) — DOCTRINE, BATTLE_BILL, WATCH_BILL, BREVITY, RATING_PROGRESSION, GLOSSARY

## Status

`v0.1.0` tagged 2026-04-27. See
[`CHANGELOG.md`](https://github.com/boylec/bluewater/blob/main/CHANGELOG.md)
for the full inventory and known unfinished items.

## License

MIT.
