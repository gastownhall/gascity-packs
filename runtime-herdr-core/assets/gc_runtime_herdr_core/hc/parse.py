"""Readers from hc's decoded JSON results to the typed records of :mod:`.types`.

Tolerant of fields they do not read, strict on the ones they do.
``terminal.list``'s ``machines`` is not read at all: hc v0.1.19 omits it when
empty although its schema requires it (hc #190). Errors are
:class:`~..rpp.jsonval.JsonShapeError`, naming the field, never its value.
"""

from __future__ import annotations

from .types import (
    CoreInfo,
    Foreground,
    HelloResult,
    HolderInfo,
    InterruptResult,
    KeysResult,
    ListResult,
    ProgramStatus,
    ReadResult,
    RemoveResult,
    SendResult,
    StatusResult,
    StopResult,
    Terminal,
)
from ..rpp.jsonval import JsonObject


def _core(doc: JsonObject) -> CoreInfo:
    return CoreInfo(id=doc.req_str("id"), name=doc.req_str("name"))


def _holder(doc: JsonObject) -> HolderInfo:
    return HolderInfo(
        pid=doc.req_int("pid"),
        instance=doc.req_str("instance"),
        current=doc.req_bool("current"),
        terminals=doc.req_int("terminals"),
    )


def _program_status(doc: JsonObject) -> ProgramStatus:
    return ProgramStatus(
        state=doc.req_str("state"),
        kind=doc.opt_str("kind"),
        app=doc.str_or("app", ""),
        progress=doc.opt_int("progress"),
    )


def _foreground(doc: JsonObject) -> Foreground:
    return Foreground(
        pid=doc.req_int("pid"),
        name=doc.req_str("name"),
        argv=doc.str_tuple("argv", required=True),
        cwd=doc.req_str("cwd"),
    )


def _terminal(doc: JsonObject) -> Terminal:
    foreground = doc.opt_obj("foreground")
    status = doc.opt_obj("status")
    return Terminal(
        address=doc.req_str("address"),
        labels=doc.str_map("labels", required=True),
        argv=doc.str_tuple("argv", required=True),
        cwd=doc.req_str("cwd"),
        state=doc.req_str("state"),
        created_ms=doc.req_int("created_ms"),
        screen=doc.req_str("screen"),
        cols=doc.req_int("cols"),
        rows=doc.req_int("rows"),
        name=doc.opt_str("name"),
        pid=doc.opt_int("pid"),
        foreground=None if foreground is None else _foreground(foreground),
        reason=doc.opt_str("reason"),
        exit_code=doc.opt_int("exit_code"),
        signal=doc.opt_int("signal"),
        finished_ms=doc.opt_int("finished_ms"),
        keep=doc.bool_or("keep", False),
        parent=doc.opt_str("parent"),
        status=None if status is None else _program_status(status),
        records={key: _program_status(record) for key, record in doc.obj_map("records").items()},
        reported=doc.bool_or("reported", False),
        status_ms=doc.opt_int("status_ms"),
        turn=doc.int_or("turn", 0),
    )


def parse_terminal(value: object) -> Terminal:
    """``terminal.run|get|kill|label|keep``."""
    return _terminal(JsonObject.of(value))


def parse_list(value: object) -> ListResult:
    """``terminal.list``."""
    doc = JsonObject.of(value)
    return ListResult(
        terminals=tuple(_terminal(entry) for entry in doc.obj_tuple("terminals", required=True)),
        hidden_finished=doc.req_int("hidden_finished"),
    )


def parse_hello(value: object) -> HelloResult:
    doc = JsonObject.of(value)
    return HelloResult(
        generation=doc.req_int("generation"),
        version=doc.req_str("version"),
        core=_core(doc.req_obj("core")),
        framed=doc.req_bool("framed"),
        methods=doc.str_tuple("methods", required=True),
        features=doc.str_tuple("features", required=True),
    )


def parse_status(value: object) -> StatusResult:
    """``server.status``."""
    doc = JsonObject.of(value)
    holder = doc.opt_obj("holder")
    return StatusResult(
        core=_core(doc.req_obj("core")),
        version=doc.req_str("version"),
        pid=doc.req_int("pid"),
        uptime_ms=doc.req_int("uptime_ms"),
        holder=None if holder is None else _holder(holder),
        holders=tuple(_holder(entry) for entry in doc.obj_tuple("holders", required=True)),
        live=doc.req_int("live"),
        finished=doc.req_int("finished"),
        installed_by=doc.opt_str("installed_by"),
    )


def parse_stop(value: object) -> StopResult:
    """``server.stop``."""
    return StopResult(stopped=JsonObject.of(value).req_bool("stopped"))


def parse_send(value: object) -> SendResult:
    doc = JsonObject.of(value)
    return SendResult(turn=doc.req_int("turn"), status=doc.opt_str("status"), started=doc.opt_bool("started"))


def parse_keys(value: object) -> KeysResult:
    doc = JsonObject.of(value)
    return KeysResult(turn=doc.req_int("turn"), status=doc.opt_str("status"))


def parse_interrupt(value: object) -> InterruptResult:
    doc = JsonObject.of(value)
    return InterruptResult(outcome=doc.req_str("outcome"), key=doc.req_str("key"))


def parse_read(value: object) -> ReadResult:
    doc = JsonObject.of(value)
    return ReadResult(
        text=doc.req_str("text"),
        how=doc.req_str("how"),
        complete=doc.req_bool("complete"),
        why=doc.opt_str("why"),
    )


def parse_remove(value: object) -> RemoveResult:
    """``terminal.rm``."""
    return RemoveResult(removed=JsonObject.of(value).req_str("removed"))
