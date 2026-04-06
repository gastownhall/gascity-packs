# CASS Pack

Search past coding-agent sessions with
[`cass`](https://github.com/Dicklesworthstone/coding_agent_session_search).

## What It Provides

- Claude skill overlay at `overlay/.claude/skills/search-sessions/SKILL.md`
- Shared prompt fragment at `prompts/shared/cass-search.md.tmpl`

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

## Include It

Local checkout:

```toml
[workspace]
includes = ["../packs/flywheel/cass"]
global_fragments = ["cass-search"]
install_agent_hooks = ["claude", "codex", "gemini"] # optional
```

Remote pack source:

```toml
[packs.cass]
source = "https://github.com/gastownhall/gascity-packs.git"
ref = "main"
path = "flywheel/cass"

[workspace]
includes = ["cass"]
global_fragments = ["cass-search"]
install_agent_hooks = ["claude", "codex", "gemini"] # optional
```

## Notes

- Do not run bare `cass` in agent contexts; use `--json` or `--robot`.
- If your city already defines a local `cass-search` fragment, remove or rename
  it before enabling the pack-provided fragment.
