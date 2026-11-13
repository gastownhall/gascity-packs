"""The input-outcome wire: exit 0 for a delivery (a nudge may add one
delivered_unobserved line), exit 80 with exactly one outcome line for every
other outcome (gascity ``docs/reference/exec-session-provider.md``, "Typed
input outcomes")."""

from __future__ import annotations

import json
from typing import Dict, FrozenSet, List, Tuple

import pytest

from gc_runtime_herdr_core.rpp.exitcodes import ExitCode
from gc_runtime_herdr_core.rpp.outcome import (
    DETAIL_CAP,
    INPUT_OPS,
    NON_SUCCESS_WORDS,
    OUTCOME_WORDS,
    SUCCESS_WORDS,
    InputOp,
    NUDGE_ONLY_WORDS,
    InputOutcome,
    OutcomeWord,
    allowed,
    outcome_result,
)
from gc_runtime_herdr_core.rpp.redact import Redactor

NUDGE_ONLY: FrozenSet[OutcomeWord] = frozenset({"delivered_unobserved", "unconfirmed", "busy", "pending_interaction"})


def every_allowed() -> List[Tuple[InputOp, OutcomeWord]]:
    return [(op, word) for op in INPUT_OPS for word in OUTCOME_WORDS if allowed(op, word)]


def test_the_vocabulary_is_gcs() -> None:
    assert set(OUTCOME_WORDS) == {
        "delivered",
        "delivered_unobserved",
        "unconfirmed",
        "not_sent",
        "rejected",
        "busy",
        "pending_interaction",
        "unavailable",
        "gone",
    }
    assert set(SUCCESS_WORDS) == {"delivered", "delivered_unobserved"}
    assert set(NON_SUCCESS_WORDS) == set(OUTCOME_WORDS) - set(SUCCESS_WORDS)
    assert set(INPUT_OPS) == {"nudge", "send-keys", "interrupt", "clear-scrollback"}
    assert int(ExitCode.INPUT_OUTCOME) == 80


@pytest.mark.parametrize("op", ["send-keys", "interrupt", "clear-scrollback"])
def test_nudge_only_words_are_refused_on_the_other_ops(op: InputOp) -> None:
    for word in NUDGE_ONLY:
        assert not allowed(op, word)
        with pytest.raises(ValueError):
            outcome_result(op, InputOutcome(word), Redactor())
    assert NUDGE_ONLY_WORDS == NUDGE_ONLY
    for word in frozenset(OUTCOME_WORDS) - NUDGE_ONLY:
        assert allowed(op, word)


def test_nudge_may_answer_every_word() -> None:
    assert all(allowed("nudge", word) for word in OUTCOME_WORDS)


EXIT_CODES: Dict[str, int] = {
    "delivered": 0,
    "delivered_unobserved": 0,
    "unconfirmed": 80,
    "not_sent": 80,
    "rejected": 80,
    "busy": 80,
    "pending_interaction": 80,
    "unavailable": 80,
    "gone": 80,
}


@pytest.mark.parametrize("op, word", every_allowed())
def test_every_word_has_its_exit_code(op: InputOp, word: OutcomeWord) -> None:
    result = outcome_result(op, InputOutcome(word, "why it happened"), Redactor())
    assert int(result.code) == EXIT_CODES[word]


def test_delivered_prints_nothing() -> None:
    for op in INPUT_OPS:
        result = outcome_result(op, InputOutcome("delivered", "ignored"), Redactor())
        assert result.code == ExitCode.OK and result.stdout == b"" and result.message == ""


def test_delivered_unobserved_is_exit_0_with_one_line() -> None:
    result = outcome_result("nudge", InputOutcome("delivered_unobserved", "not seen starting"), Redactor())
    assert result.code == ExitCode.OK
    assert result.stdout.endswith(b"\n") and result.stdout.count(b"\n") == 1
    assert json.loads(result.stdout) == {"outcome": "delivered_unobserved", "detail": "not seen starting"}


@pytest.mark.parametrize("op, word", [(op, word) for op, word in every_allowed() if word in NON_SUCCESS_WORDS])
def test_a_non_success_word_is_exit_80_with_exactly_one_line(op: InputOp, word: OutcomeWord) -> None:
    result = outcome_result(op, InputOutcome(word, "the reason"), Redactor())
    assert result.code == ExitCode.INPUT_OUTCOME
    lines = result.stdout.split(b"\n")
    assert lines[-1] == b"" and len(lines) == 2
    assert json.loads(lines[0]) == {"outcome": word, "detail": "the reason"}
    assert word in result.message  # stderr names it for logs


@pytest.mark.parametrize("op, word", every_allowed())
def test_no_non_success_word_is_ever_printed_on_exit_0(op: InputOp, word: OutcomeWord) -> None:
    result = outcome_result(op, InputOutcome(word, "x"), Redactor())
    if result.code == ExitCode.OK and result.stdout:
        assert json.loads(result.stdout)["outcome"] in SUCCESS_WORDS


def test_an_empty_detail_is_omitted() -> None:
    result = outcome_result("nudge", InputOutcome("gone"), Redactor())
    assert json.loads(result.stdout) == {"outcome": "gone"}


def test_the_detail_is_one_line_within_the_cap_and_redacted() -> None:
    redactor = Redactor()
    redactor.add_process_env({"ANTHROPIC_API_KEY": "sk-secret-value-123456"})
    detail = "line one\nline two\ttab\x1b[31m sk-secret-value-123456 " + "é" * 2000
    result = outcome_result("nudge", InputOutcome("not_sent", detail), redactor)
    assert result.stdout.count(b"\n") == 1
    doc = json.loads(result.stdout)
    assert "sk-secret-value-123456" not in doc["detail"]
    assert "sk-secret-value-123456" not in result.message
    assert len(doc["detail"].encode("utf-8")) <= DETAIL_CAP
    assert not any(ch < " " for ch in doc["detail"])
    assert doc["detail"].startswith("line one line two tab")
