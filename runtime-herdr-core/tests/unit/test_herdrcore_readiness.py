"""The first turn's readiness reads, against gc's (``paneShowsReadyPrompt``,
``containsStartupDialog``)."""

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
        (f"rate limit\n{GLYPH} 1. Retry\n  2. Wait\n", f"{GLYPH} ", False, True),  # a menu's cursor row is no prompt
        ("READY> \n", "READY>", False, False),
    ],
)
def test_only_a_known_dialog_withholds_the_first_turn(screen: str, prefix: str, withheld: bool, delayed: bool) -> None:
    """A bare "rate limit" mention with no prompt line (on another line)
    keeps the wait going, but its end types the turn: gc never reads those
    bare markers to judge readiness."""
    assert withholds_first_turn(screen, prefix) is withheld
    assert delays_first_turn(screen, prefix) is delayed
