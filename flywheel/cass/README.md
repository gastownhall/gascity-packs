# CASS Pack

Search past coding-agent sessions with
[`cass`](https://github.com/Dicklesworthstone/coding_agent_session_search).

## What It Provides

- Claude skill overlay at `overlay/.claude/skills/search-sessions/SKILL.md`
- Shared prompt fragment at `template-fragments/cass-search.template.md`

The overlay skill is Claude-only. The shared prompt fragment is the
recommended cross-provider path for Claude, Codex, and Gemini cities.

## Prerequisites

Install `cass` and keep it on `PATH`.

Latest release:

```bash
curl -fsSL "https://raw.githubusercontent.com/Dicklesworthstone/coding_agent_session_search/main/install.sh?$(date +%s)" \
  | bash -s -- --easy-mode --verify
```

Build from source:

```bash
git clone https://github.com/Dicklesworthstone/coding_agent_session_search.git
cd coding_agent_session_search
cargo build --release
install -m 0755 target/release/cass ~/.local/bin/cass
```

## Import It

Local checkout:

```toml
# pack.toml
[imports.cass]
source = "../packs/flywheel/cass"

[agent_defaults]
append_fragments = ["cass-search"]
```

Optional deployment hooks still belong in `city.toml`:

```toml
[workspace]
install_agent_hooks = ["claude", "codex", "gemini"] # optional
```

## Notes

- Do not run bare `cass` in agent contexts; use `--json` or `--robot`.
- If your city already defines a local `cass-search` fragment, remove or rename
  it before enabling the pack-provided fragment.
