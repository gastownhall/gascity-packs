"""Module exercising Python significance kinds (App B): nested def/class,
with blocks, and try statements surfaced under each public function.

This fixture is comfortably over the 200-LoC outline threshold so that the
emitter actually runs and the nested-construct bullets are rendered.
"""
from __future__ import annotations

import contextlib
import threading


def alpha():
    """Public function carrying a with-block, a try, a nested def and class."""
    with open("/dev/null") as handle:
        payload = handle.read()
    try:
        risky(payload)
    except ValueError:
        recover()

    def inner_helper():
        return 1

    class InnerThing:
        value = 0

    return inner_helper, InnerThing


def bravo():
    """Public function carrying a with-block, a try, a nested def and class."""
    with threading.Lock():
        guarded()
    try:
        risky(None)
    except KeyError:
        recover()

    def inner_helper():
        return 2

    class InnerThing:
        value = 1

    return inner_helper, InnerThing


def charlie():
    """Public function carrying a with-block, a try, a nested def and class."""
    with contextlib.suppress(Exception):
        maybe()
    try:
        risky(1)
    except TypeError:
        recover()

    def inner_helper():
        return 3

    class InnerThing:
        value = 2

    return inner_helper, InnerThing


def delta():
    """Public function carrying a with-block, a try, a nested def and class."""
    with open("/dev/null") as handle:
        payload = handle.read()
    try:
        risky(payload)
    except OSError:
        recover()

    def inner_helper():
        return 4

    class InnerThing:
        value = 3

    return inner_helper, InnerThing


def echo():
    """Public function carrying a with-block, a try, a nested def and class."""
    with open("/dev/null") as handle:
        payload = handle.read()
    try:
        risky(payload)
    except RuntimeError:
        recover()

    def inner_helper():
        return 5

    class InnerThing:
        value = 4

    return inner_helper, InnerThing


def risky(_x):
    raise ValueError("boom")


def recover():
    return None


def guarded():
    return None


def maybe():
    return None


FILLER_00 = 0
FILLER_01 = 1
FILLER_02 = 2
FILLER_03 = 3
FILLER_04 = 4
FILLER_05 = 5
FILLER_06 = 6
FILLER_07 = 7
FILLER_08 = 8
FILLER_09 = 9
FILLER_10 = 10
FILLER_11 = 11
FILLER_12 = 12
FILLER_13 = 13
FILLER_14 = 14
FILLER_15 = 15
FILLER_16 = 16
FILLER_17 = 17
FILLER_18 = 18
FILLER_19 = 19
FILLER_20 = 20
FILLER_21 = 21
FILLER_22 = 22
FILLER_23 = 23
FILLER_24 = 24
FILLER_25 = 25
FILLER_26 = 26
FILLER_27 = 27
FILLER_28 = 28
FILLER_29 = 29
FILLER_30 = 30
FILLER_31 = 31
FILLER_32 = 32
FILLER_33 = 33
FILLER_34 = 34
FILLER_35 = 35
PAD_000 = 0
PAD_001 = 1
PAD_002 = 2
PAD_003 = 3
PAD_004 = 4
PAD_005 = 5
PAD_006 = 6
PAD_007 = 7
PAD_008 = 8
PAD_009 = 9
PAD_010 = 10
PAD_011 = 11
PAD_012 = 12
PAD_013 = 13
PAD_014 = 14
PAD_015 = 15
PAD_016 = 16
PAD_017 = 17
PAD_018 = 18
PAD_019 = 19
PAD_020 = 20
PAD_021 = 21
PAD_022 = 22
PAD_023 = 23
PAD_024 = 24
PAD_025 = 25
PAD_026 = 26
PAD_027 = 27
PAD_028 = 28
PAD_029 = 29
PAD_030 = 30
PAD_031 = 31
PAD_032 = 32
PAD_033 = 33
PAD_034 = 34
PAD_035 = 35
PAD_036 = 36
PAD_037 = 37
PAD_038 = 38
PAD_039 = 39
PAD_040 = 40
PAD_041 = 41
PAD_042 = 42
PAD_043 = 43
PAD_044 = 44
PAD_045 = 45
PAD_046 = 46
PAD_047 = 47
PAD_048 = 48
PAD_049 = 49
PAD_050 = 50
PAD_051 = 51
PAD_052 = 52
PAD_053 = 53
PAD_054 = 54
PAD_055 = 55
PAD_056 = 56
PAD_057 = 57
PAD_058 = 58
PAD_059 = 59
