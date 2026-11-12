"""Whether an agent's screen can take its first turn, read as gc reads a pane.

gc answers an exec runtime's startup dialogs only once ``start`` has returned,
so the first turn ``start`` types must never land in one: a dialog marks its
selected option with the prompt glyph (``❯ 1. No, exit``), and the turn's
Enter would pick it.

* :func:`shows_ready_prompt` is gascity's ``paneShowsReadyPrompt``
  (``internal/runtime/tmux/tmux.go``): the bottom-most line showing the
  prefix is the live composer (lines above it are past turns), NBSP reads as
  a space, a leading ``│``/``┃`` box border is skipped, the bare glyph counts,
  and the cursor row of a numbered menu is no prompt.
* :func:`shows_dialog` is its ``containsStartupDialog``
  (``internal/runtime/dialog.go``), with the same markers. ``start`` does
  not call it: it is the gc reference the tests pin, which the two
  functions below narrow.
* :func:`withholds_first_turn` is what keeps the first turn back: a dialog
  gc knows, a bare "rate limit" mention among them only on a menu (gc's
  provider rate-limit screen, or beside a numbered menu's cursor row). Once
  ``start`` returns, gc's startup pass answers any screen with a bare
  marker "Stop" (Down, Enter), so the turn's Enter would pick the menu's
  selected option first. A bare mention with no menu (a status line's, a
  tip's) withholds nothing: gc never reads those markers to judge
  readiness.
* :func:`delays_first_turn`: a bare mention with no prompt line (on a line
  of its own) may be a rate-limit screen gc's markers miss, so the wait
  goes on; its end types the turn.
"""

from __future__ import annotations

from typing import Final, Optional, Sequence, Tuple

NBSP: Final = "\u00a0"
BOX_BORDERS: Final = ("│", "┃")
PROMPT_GLYPHS: Final = ("❯", "›", ">")
PROMPT_ENDINGS: Final = (">", "$", "%", "#", "❯", "›")
DIGITS: Final = "0123456789"

DIALOGS: Final[Tuple[Tuple[Tuple[str, ...], ...], ...]] = (
    (("Choose the text style",), ("/theme",)),
    (("Resume from summary",), ("Resume full session as-is",), ("Enter to confirm",)),
    (("Update available!",), ("Skip until next version",), ("Press enter to continue",)),
    (
        (
            "Trust this folder?",
            "trust this folder",
            "Quick safety check",
            "Do you trust the contents of this directory?",
            "Do you trust the files in this folder?",
            "Trust project folder?",
        ),
    ),
    (("Allow external CLAUDE.md",), ("allow external imports",)),
    (("New MCP server found",), ("Use this and all future MCP servers",)),
    (
        ("Hooks need review", "hooks need review"),
        ("Trust all and continue", "trust all"),
        ("Continue without trusting", "enter to review hooks"),
    ),
    (("Bypass Permissions mode",),),
    (("Detected a custom API key in your environment", "Do you want to use this API key?"),),
)
"""gc's startup dialogs but the rate limit: a screen shows one when, for each
group of markers, it shows one of them."""
RATE_LIMIT_DIALOG: Final = ("Usage limit reached", "You've hit your limit", "/rate-limit-options")
BARE_RATE_LIMIT: Final = ("rate limit", "Rate limit")
RATE_LIMIT: Final[Tuple[str, ...]] = RATE_LIMIT_DIALOG + BARE_RATE_LIMIT
"""gc's ``ContainsRateLimitDialog`` markers (:func:`shows_dialog`, the gc
reference the tests pin)."""
RATE_LIMIT_MENU: Final = ("Keep trying", "Stop")
"""The options gc's ``ContainsProviderRateLimitScreen`` reads beside a
"rate limit" mention, in any case: a provider's rate-limit menu."""
CODEX_BANNER: Final = "OpenAI Codex"
CODEX_STATUS_SEPARATOR: Final = " · "


def shows_ready_prompt(screen: str, prefix: str) -> bool:
    """The screen's live composer shows ``prefix`` and is no menu's cursor row."""
    lines = screen.split("\n")
    for index in range(len(lines) - 1, -1, -1):
        if _prompt_rest(lines[index], prefix) is not None:
            return not _menu_cursor_row(lines, index, prefix)
    return False


def shows_dialog(screen: str) -> bool:
    """The screen shows a startup dialog gc knows. A rate-limit marker counts
    unless Codex has finished starting (gc's ``ContainsRateLimitDialog``).
    Not used by ``start``: the gc reference the tests pin."""
    return _named_dialog(screen) or _rate_limited(screen, RATE_LIMIT)


def withholds_first_turn(screen: str, prefix: str) -> bool:
    """The screen shows a dialog the first turn must not land in: one gc
    knows, a bare "rate limit" mention only on a menu (:func:`_rate_limit_menu`;
    with none, see :func:`delays_first_turn`)."""
    return _named_dialog(screen) or _rate_limited(screen, RATE_LIMIT_DIALOG) or _rate_limit_menu(screen, prefix)


def delays_first_turn(screen: str, prefix: str) -> bool:
    """The screen is not ready for the first turn, though no dialog holds it
    back for good: a dialog (:func:`withholds_first_turn`), or a bare "rate
    limit" mention with no prompt line on another line (the ready prompt
    when ``prefix`` is set, else any prompt line)."""
    if withholds_first_turn(screen, prefix):
        return True
    return _rate_limited(screen, BARE_RATE_LIMIT) and not _shows_prompt_line(screen, prefix)


def _named_dialog(screen: str) -> bool:
    return any(all(any(marker in screen for marker in group) for group in dialog) for dialog in DIALOGS)


def _rate_limited(screen: str, markers: Sequence[str]) -> bool:
    """A rate-limit marker shows, unless Codex has finished starting."""
    if CODEX_BANNER in screen and _codex_settled(screen):
        return False
    return any(marker in screen for marker in markers)


def _rate_limit_menu(screen: str, prefix: str) -> bool:
    """A "rate limit" mention on a menu, unless Codex has finished starting:
    gc's provider rate-limit screen (``ContainsProviderRateLimitScreen``: the
    mention in any case, with :data:`RATE_LIMIT_MENU`), or a bare marker
    beside a numbered menu's cursor row, read with ``prefix`` or a prompt
    glyph. A numbered list with no cursor row (a tip's) is no menu."""
    if CODEX_BANNER in screen and _codex_settled(screen):
        return False
    if "rate limit" in screen.lower() and all(option in screen for option in RATE_LIMIT_MENU):
        return True
    return _rate_limited(screen, BARE_RATE_LIMIT) and _shows_menu_cursor(screen, prefix)


def _shows_menu_cursor(screen: str, prefix: str) -> bool:
    """Some line is a numbered menu's cursor row, marked by ``prefix`` or by
    a prompt glyph and a space."""
    lines = screen.split("\n")
    cursors = tuple(glyph + " " for glyph in PROMPT_GLYPHS) + ((prefix,) if prefix else ())
    return any(_menu_cursor_row(lines, index, cursor) for cursor in cursors for index in range(len(lines)))


def _shows_prompt_line(screen: str, prefix: str) -> bool:
    """A prompt line shows, other than one holding a bare rate-limit marker."""
    lines = [line for line in screen.split("\n") if not any(marker in line for marker in BARE_RATE_LIMIT)]
    if prefix:
        return shows_ready_prompt("\n".join(lines), prefix)
    return any(_prompt_indicator(line) for line in lines)


def _prompt_rest(line: str, prefix: str) -> Optional[str]:
    """``promptLineRest``: what follows ``prefix`` and its spaces on ``line``
    ("" for the bare glyph), or None when the line does not show it."""
    if not prefix:
        return None
    text = line.strip().replace(NBSP, " ")
    prefix = prefix.replace(NBSP, " ")
    bare = prefix.strip()
    for candidate in (text, _strip_border(text)):
        if candidate.startswith(prefix):
            return candidate[len(prefix) :].lstrip(" ")
        if bare and candidate == bare:
            return ""
    return None


def _menu_cursor_row(lines: Sequence[str], index: int, prefix: str) -> bool:
    """``isMenuCursorRow``: the prompt line ``lines[index]`` reads "N. " and the
    nearest non-blank line above or below it is option N-1 or N+1 (options
    not selected carry no glyph), so a draft starting "1. " is still a prompt."""
    rest = _prompt_rest(lines[index], prefix)
    number = None if rest is None else _option_number(rest)
    if number is None:
        return False
    return any(_neighbour_option(lines, index, step) in (number - 1, number + 1) for step in (-1, 1))


def _neighbour_option(lines: Sequence[str], index: int, step: int) -> Optional[int]:
    """The option number of the nearest non-blank line from ``lines[index]`` in direction ``step``."""
    at = index + step
    while 0 <= at < len(lines):
        row = _strip_border(lines[at].replace(NBSP, " ").strip())
        if row:
            return _option_number(row)
        at += step
    return None


def _option_number(text: str) -> Optional[int]:
    """``menuOptionNumber``: N for a text starting with ASCII digits and ". "."""
    digits = len(text) - len(text.lstrip(DIGITS))
    if digits == 0 or not text.startswith(". ", digits):
        return None
    return int(text[:digits])


def _strip_border(text: str) -> str:
    """``stripLeadingBoxBorder``: a leading box border and the blanks around it."""
    text = text.lstrip(" \t")
    if text[:1] in BOX_BORDERS:
        return text[1:].lstrip(" \t")
    return text


def _codex_settled(screen: str) -> bool:
    """``codexStartupSettled``: Codex drew its status line ("<model> · <dir>")
    under its bottom-most prompt, which it does once startup is over."""
    lines = screen.split("\n")
    for index in range(len(lines) - 1, -1, -1):
        if _prompt_indicator(lines[index]):
            return any(CODEX_STATUS_SEPARATOR in below for below in lines[index + 1 :])
    return False


def _prompt_indicator(line: str) -> bool:
    """``containsPromptIndicator`` for one line: a shell or agent prompt, its
    glyph alone or before text that is not a numbered menu row ("› 1.")."""
    text = _strip_border(line.replace(NBSP, " ").rstrip(" \t"))
    if not text:
        return False
    for glyph in PROMPT_GLYPHS:
        if text == glyph or (text.startswith(glyph + " ") and not _numbered(text[len(glyph) + 1 :])):
            return True
    return text.endswith(PROMPT_ENDINGS)


def _numbered(text: str) -> bool:
    """``isNumberedMenuRow``: digits, then a dot."""
    digits = len(text) - len(text.lstrip(DIGITS))
    return 0 < digits < len(text) and text[digits] == "."
