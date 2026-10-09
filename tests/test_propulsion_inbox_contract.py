"""Contract test for the propulsion fragment's two-queue and archive semantics.

Issue #342 names two properties this fragment has to hold, and neither is
visible to `gc lint` or to any per-pack suite: they are properties of prose.

1. Ordering. Inbox processing is never conditional on the hook being empty.
   The defect this replaces read `3. If it returns no work, process inbox`,
   which linted clean forever while letting a steady hook queue starve mail.
2. Completion semantics. Reading clears unread; archiving happens only after
   the obligation is resolved or is represented by durable tracked work.

Both are one careless edit away from regressing — the shape of the regression
is a helpful-looking simplification ("archive when you're done reading"), not a
syntax error. So the load-bearing sentences are pinned here by exact text, and
the known-bad shapes are pinned as prohibitions. An edit that drops the archive
discipline, or that reinstates hook-empty gating, turns this suite red.

Prohibitions are asserted against the same source the positive assertions read,
so a rename of the fragment file fails collection rather than passing vacuously
(see `test_fragment_source_is_where_we_think_it_is`).

Mail retention wording is pinned too. Gas City's `mail.retention_ttl` purges
read *wisp-tier* messages only when set to a nonzero duration; empty or "0"
disables the purge, and main-tier messages are preserved either way
(`internal/config/config.go` MailConfig.RetentionTTLDuration,
`internal/mail/beadmail/beadmail.go` PurgeReadMessageWisps). Guidance that
tells a seat every read message is inherently temporary is factually wrong, so
the phrasings that assert it are prohibited.

Those retention pins assert *another repo's* behavior, which is the one leg of
this doctrine the suite structurally cannot observe: if Gas City changes
retention semantics, these pins stay green while the shipped wording goes
stale. They were verified against gascity commit
4ef1f7b001e04d0ff538c751613e5a74fb3b103b (2026-07-21) at three code points --
`internal/config/config.go` (`RetentionTTL`; `RetentionTTLDuration` maps both
empty and "0" to 0), `internal/mail/beadmail/beadmail.go`
(`PurgeReadMessageWisps` lists `TierMode: TierWisps` with `read=true` only),
and `cmd/gc/wisp_gc.go` (the purge arm is gated on the TTL being > 0).
Re-check them there when this sentence is next edited.

The archive-motive prohibitions are deliberately *not* scoped to this fragment.
A seat's rendered prompt is a composition -- propulsion-* plus the city's global
fragments plus the role prompt plus the patrol formula step it is executing --
and the doctrine only holds if every one of those surfaces says the same thing.
The surface with the widest reach is not this file: `operational-awareness` is
seeded into `GlobalFragments` for every gastown city, so it lands in *every*
rendered agent prompt. This repo asserts that pairing itself
(`scripts/gascity_pack_inference_gate.py` emits
`global_fragments = ["command-glossary", "operational-awareness"]` and
`tests/test_gascity_pack_inference_gate.py` pins it); gascity's `GastownCity`
and `GastownCityWithProviders` default it. It shipped "always archive it to
keep your inbox clean" -- the exact motive #342 defect 2 is about -- straight
past the first version of this suite, because that version scanned only the
propulsion fragment.
"""

from __future__ import annotations

from pathlib import Path
import re

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
FRAGMENT = REPO_ROOT / "gastown" / "template-fragments" / "propulsion.template.md"

DEFINE = re.compile(
    r'\{\{\s*define\s+"(?P<name>[^"]+)"\s*\}\}(?P<body>.*?)\{\{\s*end\s*\}\}',
    re.DOTALL,
)

# The sentences the doctrine rests on. Each is a whole thought, not a keyword,
# so a reword that keeps the meaning is a deliberate edit to this list rather
# than an accident.
LOAD_BEARING = (
    # Two queues, and the inbox is a peer of the hook.
    "you have TWO work queues and they are PEERS",
    "Inbox processing is never conditional on the hook being empty.",
    "Neither queue is the fallback for the other.",
    # The completion rule, stated once, in both directions.
    "IT IS NOT DONE UNTIL IT IS ARCHIVED, AND IT IS NOT ARCHIVABLE UNTIL IT IS RESOLVED.",
    "ARCHIVE ONLY WHEN THE OBLIGATION IS RESOLVED, OR WHEN IT IS REPRESENTED BY DURABLE TRACKED WORK",
    # Reading and archiving are different acts.
    "Reading clears the unread count.",
    "NEVER archive to clear a count.",
    # Retention, stated as the configurable behavior it is.
    "`mail.retention_ttl` purges read wisp-tier messages once it is set to a nonzero duration",
    "disables that purge entirely when it is zero or empty",
    "main-tier messages are preserved either way",
)

# Retention claims contradicting mail.retention_ttl. These stay scoped to the
# propulsion fragment, which is where the retention doctrine is stated: they are
# only wrong when said about *mail*, and a future fragment may quite correctly
# say that a worktree or a temp dir "will not persist".
PROHIBITED = (
    ("will not persist", "claims read mail is inherently temporary"),
    ("is not durable storage", "claims read mail is inherently temporary"),
    ("lifecycle-managed", "claims read mail is inherently temporary"),
)

# Shapes that are wrong on any surface telling a seat when to archive or when to
# reach its inbox. Each phrase is about mail outright — it names the inbox or the
# hook, it names the read-and-open state only a message has, or it tells the seat
# to archive, and the only thing these surfaces ever tell a seat to archive is a
# message — so scanning a superset of files cannot make it ambiguous: a file that
# carries no inbox instructions simply never matches, and the scan claims nothing
# about it.
# Matched case-insensitively: these pin a *shape*, and a mid-sentence lowercase
# restatement ("just archive after reading them") is that shape, not a new one.
# Formula-step prose is written mid-sentence more often than not, so casing is
# the thinnest drift there is. The phrases are distinctive enough that widening
# the match costs no precision.
PROHIBITED_ANYWHERE = (
    # The starvation defect: inbox work gated on an empty hook (#342 defect 1).
    ("If it returns no work, **process inbox", "inbox gated on an empty hook"),
    ("If it returns no work, check mail", "inbox gated on an empty hook"),
    # Archiving sold as a way to reach a clean count (#342 defect 2). The first
    # of these is what operational-awareness shipped into every rendered gastown
    # prompt, next to the propulsion rule forbidding exactly that motive.
    ("to keep your inbox clean", "archiving motivated by inbox hygiene, not by resolution"),
    ("Read + archive is fine", "archiving offered as a substitute for resolving"),
    ("Archive after reading", "archiving keyed to having read, not to having resolved"),
    ("Inbox should be near-empty", "backlog size offered as the archive trigger"),
    ("inbox exceeds", "backlog size offered as the archive trigger"),
    # The deacon's end-of-cycle check and the witness Mail Drain, both composed
    # with propulsion-base: archiving whatever was not handled, and archiving by
    # age in place of checking the state the message announced.
    ("Archive the rest", "archiving offered as the default for what was not handled"),
    ("archive stale", "age offered as the archive trigger, not a verified resolution"),
    # Read-and-open offered as where an owed message waits. `gc mail inbox` lists
    # unread mail only, so a message read and left open is not listed again and
    # the next cycle never reaches it. The keep-visible paths are a bead or
    # `gc mail mark-unread`.
    ("stays read and open", "read-and-open offered as a parking state the inbox never lists"),
    ("left read and open is still visible", "read-and-open claimed visible to an unread-only inbox"),
)

# Every pack surface that can tell a seat when to archive: the shared fragments,
# the role prompts composing them, and the patrol formula steps those roles run.
# Globs, so a new fragment or patrol formula is covered the day it lands — but a
# glob that stops matching turns every prohibition above into a vacuous pass, so
# REQUIRED_IN_SCAN pins the files that must be in the result.
INBOX_INSTRUCTION_GLOBS = (
    "gastown/template-fragments/*.md",
    "gastown/agents/*/prompt.template.md",
    "gastown/assets/prompts/*.template.md",
    "gastown/formulas/mol-*-patrol.toml",
)

REQUIRED_IN_SCAN = (
    "gastown/template-fragments/propulsion.template.md",
    "gastown/template-fragments/operational-awareness.template.md",
    "gastown/agents/witness/prompt.template.md",
    "gastown/assets/prompts/crew.template.md",
    "gastown/formulas/mol-deacon-patrol.toml",
    "gastown/formulas/mol-refinery-patrol.toml",
    "gastown/formulas/mol-witness-patrol.toml",
)

# Roles whose startup guidance must reach the inbox unconditionally. The other
# propulsion roles (deacon, witness, refinery, polecat, dog) run patrol wisps or
# a scripted claim block and have no startup inbox step to gate.
INBOX_STARTUP_ROLES = ("propulsion-mayor", "propulsion-crew")

# The #342 gate re-spelled. "If your hook comes back empty, process your inbox"
# is the same starvation defect as "If it returns no work", and it passed a
# check that knew only the historical words. A conditional, then the hook and
# its emptiness ("when the hook is empty") or the emptiness and then the hook
# ("if nothing is hooked"), with no `.`, `;`, `:` or `—` between them.
HOOK_EMPTY = re.compile(
    r"\b(?:if|when|while|once|after|until|unless)\b[^.;:—]*?"
    r"(?:\b(?:hook|hooked|it returns|it comes back)\b[^.;:—]*?"
    r"\b(?:no work|nothing|empty|clear)\b"
    r"|\b(?:no work|nothing)\b[^.;:—]*?\b(?:hook|hooked)\b)",
    re.IGNORECASE,
)

# The last negation in the clause leading up to a hook-empty condition. Negating
# the condition itself states the rule rather than breaking it — "not what you
# do when the hook is empty" — so that is exempt, but only when no inbox action
# sits between the negation and the condition: "never process your inbox unless
# the hook is clear" is still a gate, double negative or not.
CONDITION_NEGATED = re.compile(
    r".*(?:\b(?:not|never|cannot)\b|n't\b)(?P<between>.*)", re.IGNORECASE | re.DOTALL
)


def fragment_text() -> str:
    return FRAGMENT.read_text(encoding="utf-8")


def fragment_blocks() -> dict[str, str]:
    return {m.group("name"): m.group("body") for m in DEFINE.finditer(fragment_text())}


def flat(text: str) -> str:
    """Collapse wrapping so a pinned sentence survives a reflow of the prose.

    The pins are about wording, not about where the 80th column lands; a
    contributor rewrapping a paragraph should not have to touch this file.

    Markdown blockquote markers come off first. The archive rule is a two-line
    `>` quote, so collapsing whitespace alone leaves a `> ` stranded mid-pin:
    joining the quote onto one line renders identically but would fail as if
    the sentence had been deleted, which is the exact false positive this
    helper exists to prevent.
    """
    return re.sub(r"\s+", " ", re.sub(r"(?m)^[ \t]*> ?", "", text))


def test_fragment_source_is_where_we_think_it_is() -> None:
    """Without this, a moved or renamed fragment makes every check below vacuous."""
    assert FRAGMENT.is_file(), f"propulsion fragment not found at {FRAGMENT}"
    assert 'define "propulsion-base"' in fragment_text()


@pytest.mark.parametrize("sentence", LOAD_BEARING)
def test_base_fragment_keeps_load_bearing_sentence(sentence: str) -> None:
    assert sentence in flat(fragment_blocks()["propulsion-base"]), (
        "propulsion-base no longer carries a load-bearing sentence from #342. "
        "If this is intentional, change the sentence here in the same commit "
        f"and say why in the message: {sentence!r}"
    )


@pytest.mark.parametrize(("phrase", "why"), PROHIBITED)
def test_fragment_avoids_known_bad_phrasing(phrase: str, why: str) -> None:
    assert phrase not in flat(fragment_text()), f"{phrase!r} reintroduces: {why}"


def inbox_instruction_sources() -> dict[str, str]:
    """Text of every scanned surface, keyed by repo-relative path."""
    found: dict[str, str] = {}
    for pattern in INBOX_INSTRUCTION_GLOBS:
        for path in sorted(REPO_ROOT.glob(pattern)):
            found[path.relative_to(REPO_ROOT).as_posix()] = path.read_text(encoding="utf-8")
    return found


def locate(text: str, phrase: str) -> str:
    """Best-effort line reference for a phrase found in the flattened file.

    Matched casefolded, like the scan that calls it, so a lowercase restatement
    still resolves to the line carrying it instead of degrading to "(wrapped
    across lines)" and sending the reader hunting.
    """
    needle = phrase.casefold()
    lines = text.splitlines()
    for lineno, line in enumerate(lines, start=1):
        if needle in flat(line).casefold():
            return f"{lineno}: {line.strip()}"
    # The phrase survived a line wrap; the pair scan recovers the common case.
    for lineno in range(2, len(lines) + 1):
        if needle in flat("\n".join(lines[lineno - 2 : lineno])).casefold():
            return f"{lineno - 1}-{lineno}: {lines[lineno - 2].strip()}"
    return "(wrapped across lines)"


def startup_blocks(steps: str) -> list[str]:
    """Split startup guidance into top-level markdown blocks.

    A blank line ends a block only when the next non-blank line is unindented.
    That is the rule markdown itself uses for list continuations, and both
    directions matter here:

    * A step whose second paragraph is written as a blank line plus an indented
      paragraph stays one block, so a hook-empty gate added there is still read
      against the inbox instruction it qualifies. Writing the continuation that
      way is the most natural formatting for the regression this guards.
    * An unrelated later paragraph — a role's closing "no work" prose — begins a
      block of its own and cannot accrete onto a step above it.

    Blocks are not required to be numbered. The mayor states its inbox rules in
    an unnumbered `**Step 4 — inbox triage**` block, which is precisely where a
    future hook-empty gate would be written, so a walk that only followed
    numbered steps would not be looking where the instructions live.
    """
    blocks: list[list[str]] = []
    current: list[str] = []
    pending_blank = False
    for line in steps.splitlines():
        if not line.strip():
            pending_blank = True
            continue
        if pending_blank:
            pending_blank = False
            if line[:1].isspace():
                current.append("")
            elif current:
                blocks.append(current)
                current = []
        current.append(line)
    if current:
        blocks.append(current)
    return ["\n".join(block) for block in blocks]


def hook_empty_gates(block: str) -> list[str]:
    """Hook-empty conditions in a block that are not negated where they stand."""
    text = flat(block)
    gates = []
    for match in HOOK_EMPTY.finditer(text):
        clause = re.split(r"[.;:—,(]", text[: match.start()])[-1]
        negated = CONDITION_NEGATED.match(clause)
        if negated and not re.search(r"\binbox\b|\bmail\b", negated["between"], re.IGNORECASE):
            continue
        gates.append(match.group(0))
    return gates


def test_prohibition_scan_covers_the_surfaces_it_claims_to() -> None:
    """A glob that stops matching would make every prohibition below vacuous."""
    found = inbox_instruction_sources()
    missing = [rel for rel in REQUIRED_IN_SCAN if rel not in found]
    assert not missing, (
        "the archive-motive scan no longer reaches surfaces it is responsible "
        f"for — a moved or renamed file silences it: {missing}"
    )


@pytest.mark.parametrize(("phrase", "why"), PROHIBITED_ANYWHERE)
def test_no_surface_teaches_a_banned_archive_shape(phrase: str, why: str) -> None:
    needle = phrase.casefold()
    offenders = [
        f"{rel}:{locate(text, phrase)}"
        for rel, text in sorted(inbox_instruction_sources().items())
        if needle in flat(text).casefold()
    ]
    assert not offenders, (
        f"{phrase!r} reintroduces: {why}. Each surface below is composed into a "
        "rendered agent prompt alongside the propulsion rule forbidding it:\n"
        + "\n".join(offenders)
    )


@pytest.mark.parametrize("role", INBOX_STARTUP_ROLES)
def test_startup_reaches_inbox_without_an_empty_hook(role: str) -> None:
    """The step that reaches the inbox must not sit behind a hook-empty branch."""
    body = fragment_blocks()[role]
    startup = body.split("**Your startup behavior:**", 1)
    assert len(startup) == 2, f"{role} has no startup block to check"
    steps = startup[1]

    inbox_lines = [
        line
        for line in steps.splitlines()
        if re.search(r"\binbox\b|\bmail\b", line, re.IGNORECASE)
    ]
    assert inbox_lines, f"{role} startup never reaches the inbox"

    # Check each block that reaches the inbox against the whole block it sits
    # in, so a conditional on either side of the instruction still counts as the
    # gate on it. Blocks bound the reading: an unrelated "no work" sentence
    # elsewhere in the role body is a block of its own and cannot fail this.
    # Deliberately strict within a block: startup prose that puts "no work" and
    # the inbox in one breath reads as a gate whether or not it meant to, which
    # is how #342 defect 1 was written. Say it in two blocks, or say it the way
    # propulsion-mayor step 3 does ("not what you do when the hook is empty").
    # "no work" is the historical spelling; HOOK_EMPTY is the same gate in the
    # other words it would be written with today.
    for block in startup_blocks(steps):
        if not re.search(r"\binbox\b|\bmail\b", block, re.IGNORECASE):
            continue
        assert "no work" not in flat(block), (
            f"{role}: inbox processing is gated on an empty hook — this is the "
            f"#342 starvation defect.\n{block}"
        )
        gates = hook_empty_gates(block)
        assert not gates, (
            f"{role}: inbox processing is gated on an empty hook ({gates}) — this "
            f"is the #342 starvation defect, reworded.\n{block}"
        )


@pytest.mark.parametrize("role", INBOX_STARTUP_ROLES)
def test_inbox_startup_states_the_archive_precondition(role: str) -> None:
    body = fragment_blocks()[role]
    assert "resolved or represented by durable tracked work" in flat(body), (
        f"{role} states an inbox step without the archive precondition; the two "
        "have to travel together or a seat reads 'process the inbox' as "
        "'empty the inbox'."
    )


def test_every_role_composes_the_base_fragment() -> None:
    """No role may carry inbox guidance that skips the shared rule."""
    blocks = fragment_blocks()
    roles = [name for name in blocks if name != "propulsion-base"]
    assert roles, "no propulsion role fragments found"
    for role in roles:
        assert '{{ template "propulsion-base" . }}' in blocks[role], (
            f"{role} does not compose propulsion-base"
        )


def test_archive_rule_is_stated_once_in_the_base() -> None:
    """#342 asks for one concise rule; two phrasings is how they drift apart."""
    base = fragment_blocks()["propulsion-base"]
    assert flat(base).count("ARCHIVE ONLY WHEN THE OBLIGATION IS RESOLVED") == 1
