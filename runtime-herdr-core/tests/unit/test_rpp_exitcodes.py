"""The RPP v0 exit-code vocabulary (exec-session-provider.md "Exit Codes")."""

from __future__ import annotations

from gc_runtime_herdr_core.rpp.exitcodes import ExitCode


def test_exit_codes_are_exactly_the_rpp_v0_table() -> None:
    assert {code.name: int(code) for code in ExitCode} == {
        "OK": 0,
        "FAIL": 1,
        "UNKNOWN_OP": 2,
        "NO_SCREEN": 66,
        "FRESH_COLLISION": 73,
        "TEMPFAIL": 75,
    }


def test_exit_codes_are_ints_for_sys_exit() -> None:
    assert int(ExitCode.NO_SCREEN) == 66
    assert isinstance(ExitCode.UNKNOWN_OP, int)
