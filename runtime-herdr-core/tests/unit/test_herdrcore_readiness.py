"""The first turn's readiness reads, against gc's (``paneShowsReadyPrompt``,
``containsStartupDialog``, ``ContainsProviderRateLimitScreen``)."""

from __future__ import annotations

import pytest

from gc_runtime_herdr_core.herdrcore.readiness import delays_first_turn, shows_dialog, shows_ready_prompt, withholds_first_turn

GLYPH = "❯"
NBSP = "\u00a0"


@pytest.mark.parametrize(
    "screen, prefix, ready",
    [
        ("booting\nREADY> \n", "READY>", True),
        ("booting\n", "READY>", False),
        ("READY>\n", "", False),
        (f"{GLYPH}{NBSP}Try it\n", f"{GLYPH} ", True),  # Claude's composer: NBSP after the glyph
        (f"{GLYPH}\n", f"{GLYPH} ", True),  # the bare glyph
        (f"│ {GLYPH} Try it │\n", f"{GLYPH} ", True),  # a boxed composer
        (f"{GLYPH} 1. No, exit\n  2. Yes, I accept\n", f"{GLYPH} ", False),  # a menu's cursor row
        (f"  1. Yes, proceed\n{GLYPH} 2. No, exit\n", f"{GLYPH} ", False),
        (f"{GLYPH} 1. Yes, proceed\n\n  2. No, exit\n", f"{GLYPH} ", False),  # blank rows between options
        (f"{GLYPH} 1. fix the lint\n", f"{GLYPH} ", True),  # a draft that starts with "1. "
        (f"{GLYPH} 1. fix the lint\n  4. later\n", f"{GLYPH} ", True),  # no neighbouring option
        (f"{GLYPH} 1. Yes\n  2. No\n\n{GLYPH} \n", f"{GLYPH} ", True),  # the bottom-most prompt decides
        (f"{GLYPH} earlier turn\n{GLYPH} 1. Yes\n  2. No\n", f"{GLYPH} ", False),
    ],
)
def test_the_ready_prompt_is_read_as_gc_reads_it(screen: str, prefix: str, ready: bool) -> None:
    assert shows_ready_prompt(screen, prefix) is ready


@pytest.mark.parametrize(
    "screen, dialog",
    [
        (f"Do you trust the files in this folder?\n{GLYPH} 1. Yes, proceed\n  2. No, exit\n", True),
        (f"WARNING: Claude Code running in Bypass Permissions mode\n{GLYPH} 1. No, exit\n  2. Yes, I accept\n", True),
        ("Detected a custom API key in your environment\n", True),
        ("Choose the text style\nTo change this later, run /theme\n", True),
        ("Choose the text style\n", False),  # every marker of a group must show
        ("Hooks need review\nTrust all and continue\nContinue without trusting\n", True),
        ("Hooks need review\nTrust all and continue\n", False),
        ("You've hit your limit\n", True),
        (f"{GLYPH} Try it\n", False),
        # A Codex screen that finished starting (its status line under the
        # composer) shows no rate-limit dialog, whatever its text says.
        ("OpenAI Codex\n› ask about the rate limit\n  gpt-5 · ~/repo\n", False),
        ("OpenAI Codex\n› ask about the rate limit\n", True),
        ("OpenAI Codex\nrate limit\n› 1. Retry\n  enter confirm · esc skip\n", True),
    ],
)
def test_startup_dialogs_are_read_as_gc_reads_them(screen: str, dialog: bool) -> None:
    assert shows_dialog(screen) is dialog


@pytest.mark.parametrize(
    "screen, prefix, withheld, delayed",
    [
        (f"Do you trust the files in this folder?\n{GLYPH} 1. Yes, proceed\n  2. No, exit\n", f"{GLYPH} ", True, True),
        ("You've hit your limit\nREADY> \n", "READY>", True, True),  # a rate-limit dialog, prompt or not
        ("READY> \n  rate limit: 40% used\n", "READY>", False, False),  # a status line under the prompt
        ("booting\n  rate limit: 40% used\n", "READY>", False, True),  # no prompt yet: wait, never withhold
        (f"{GLYPH} \n  Rate limit resets at 5pm\n", "", False, False),  # any prompt line, with no prefix
        ("Rate limit reached\nretrying...\n", "", False, True),
        ("Rate limit reached: 100%\n", "", False, True),  # the marker's own line is no prompt line
        ("Welcome\nTip: avoid hitting the rate limit by...\n", f"{GLYPH} ", False, True),
        ("Tips:\n1. mind the rate limit\n2. use /compact\n", f"{GLYPH} ", False, True),  # a list with no cursor row
        # A bare mention on a menu: gc's startup pass answers it "Stop", so
        # the turn's Enter would pick the selected option first.
        ("Rate limit reached\n1. Keep trying\n2. Stop\n", "", True, True),  # gc's provider rate-limit screen
        (f"Rate limit reached\n{GLYPH} 1. Keep trying\n  2. Stop\n", f"{GLYPH} ", True, True),
        ("RATE LIMIT REACHED\n1. Keep trying\n2. Stop\n", "", True, True),  # in any case, as gc reads it
        ("Usage limit reached for gemini-3-flash-preview.\n1. Keep trying\n2. Stop\n", "", True, True),
        (f"rate limit\n{GLYPH} 1. Retry\n  2. Wait\n", f"{GLYPH} ", True, True),  # a menu's cursor row is no prompt
        (f"rate limit\n{GLYPH} 1. Retry\n  2. Wait\n", "", True, True),  # the glyph marks it with no prefix
        ("rate limit\nREADY> 1. Retry\n  2. Wait\n", "READY>", True, True),  # and so does the prefix
        # A Codex screen that finished starting shows no rate-limit menu, whatever its draft says.
        ("OpenAI Codex\n› why did Rate limit reached show Keep trying and Stop\n  gpt-5 · ~/repo\n", "", False, False),
        ("READY> \n", "READY>", False, False),
    ],
)
def test_only_a_known_dialog_withholds_the_first_turn(screen: str, prefix: str, withheld: bool, delayed: bool) -> None:
    """A bare "rate limit" mention withholds the turn only on a menu (gc's
    provider rate-limit screen, or beside a numbered menu's cursor row);
    with none and no prompt line (on another line) it keeps the wait going,
    but its end types the turn: gc never reads those bare markers to judge
    readiness."""
    assert withholds_first_turn(screen, prefix) is withheld
    assert delays_first_turn(screen, prefix) is delayed
