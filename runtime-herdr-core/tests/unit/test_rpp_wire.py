"""Typed RPP v0 + observe.v1 wire (exec-session-provider.md; gc exec/json.go,
exec/observe.go and exec/inventory.go are the decoders these shapes must satisfy)."""

from __future__ import annotations

import json

import pytest

from gc_runtime_herdr_core.rpp.wire import (
    IDENTITY_KEYS,
    BoxObject,
    CopyFile,
    Handshake,
    InventoryAnswer,
    InventoryEntry,
    ObserveAnswer,
    WatchStartupEvent,
    WireError,
    encode_bool,
    parse_kill_object_request,
    parse_start_config,
    rfc3339_ms,
)

OBJ = BoxObject(id="t7", created="2026-11-09T10:00:00.123Z")


# --- handshake -------------------------------------------------------------


def test_handshake_encodes_compact_json() -> None:
    hs = Handshake(capabilities=("observe.v1", "report-attachment"), locality="local")
    assert json.loads(hs.encode()) == {
        "version": 0,
        "capabilities": ["observe.v1", "report-attachment"],
        "locality": "local",
    }
    assert "\n" not in hs.encode()


def test_handshake_omits_an_unset_locality() -> None:
    assert json.loads(Handshake(capabilities=(), locality=None).encode()) == {"version": 0, "capabilities": []}


# --- start config ----------------------------------------------------------


def test_start_config_reads_every_field_gc_sends() -> None:
    doc = {
        "work_dir": "/w",
        "command": "claude --dangerously-skip-permissions",
        "lifecycle": "one_shot",
        "env": {"GC_AGENT": "mayor", "GC_CONTROLLER_TOKEN": ""},
        "process_names": ["claude", "node"],
        "nudge": "hello",
        "ready_prompt_prefix": "> ",
        "ready_delay_ms": 1500,
        "pre_start": ["mkdir -p /w"],
        "session_setup": ["true"],
        "session_setup_script": "/s.sh",
        "session_live": ["echo live"],
        "pack_overlay_dirs": ["/p1", "/p2"],
        "overlay_dir": "/o",
        "copy_files": [{"src": "/a", "rel_dst": "b"}, {"src": "/c"}],
        "work_dir_exclude": [".gc/"],
        "fresh_only": True,
    }
    cfg = parse_start_config(json.dumps(doc).encode())
    assert cfg.work_dir == "/w"
    assert cfg.command == "claude --dangerously-skip-permissions"
    assert cfg.lifecycle == "one_shot"
    assert dict(cfg.env) == {"GC_AGENT": "mayor", "GC_CONTROLLER_TOKEN": ""}
    assert cfg.process_names == ("claude", "node")
    assert cfg.nudge == "hello"
    assert cfg.ready_prompt_prefix == "> "
    assert cfg.ready_delay_ms == 1500
    assert cfg.pre_start == ("mkdir -p /w",)
    assert cfg.session_setup == ("true",)
    assert cfg.session_setup_script == "/s.sh"
    assert cfg.session_live == ("echo live",)
    assert cfg.pack_overlay_dirs == ("/p1", "/p2")
    assert cfg.overlay_dir == "/o"
    assert cfg.copy_files == (CopyFile(src="/a", rel_dst="b"), CopyFile(src="/c", rel_dst=""))
    assert cfg.work_dir_exclude == (".gc/",)
    assert cfg.fresh_only is True


def test_start_config_fields_are_all_optional() -> None:
    cfg = parse_start_config(b"{}")
    assert cfg.command == ""
    assert dict(cfg.env) == {}
    assert cfg.process_names == ()
    assert cfg.ready_delay_ms == 0
    assert cfg.fresh_only is False


def test_start_config_ignores_unknown_fields() -> None:
    cfg = parse_start_config(b'{"command":"x","newer_flag":true,"newer_object":{"k":"v"},"future":[1,2]}')
    assert cfg.command == "x"


@pytest.mark.parametrize(
    ("doc", "field"),
    [
        ({"command": 123}, "command"),
        ({"env": {"API_TOKEN": 5}}, "env.API_TOKEN"),
        ({"env": ["sk-not-an-object"]}, "env"),
        ({"process_names": "sk-secret-value"}, "process_names"),
        ({"ready_delay_ms": "5"}, "ready_delay_ms"),
        ({"ready_delay_ms": True}, "ready_delay_ms"),
        ({"fresh_only": "yes"}, "fresh_only"),
        ({"copy_files": [{"rel_dst": "b"}]}, "copy_files[0].src"),
    ],
)
def test_start_config_refuses_mistyped_fields_without_echoing_values(doc: dict[str, object], field: str) -> None:
    with pytest.raises(WireError) as caught:
        parse_start_config(json.dumps(doc).encode())
    message = str(caught.value)
    assert field in message
    assert "sk-" not in message


@pytest.mark.parametrize("data", [b"", b"not json", b"[1,2]", b'"text"', b"{} {}"])
def test_start_config_must_be_one_object(data: bytes) -> None:
    with pytest.raises(WireError):
        parse_start_config(data)


# --- kill-object -----------------------------------------------------------


def test_kill_object_request_parses() -> None:
    req = parse_kill_object_request(b'{"object":{"id":"t7","created":"c"},"mode":"zombie","agent_pid":"4242"}')
    assert req.box == BoxObject(id="t7", created="c")
    assert req.mode == "zombie"
    assert req.agent_pid == "4242"
    corpse = parse_kill_object_request(b'{"object":{"id":"t7","created":"c"},"mode":"corpse"}')
    assert corpse.agent_pid == ""


@pytest.mark.parametrize(
    "data",
    [
        b'{"mode":"corpse"}',
        b'{"object":{"id":"","created":"c"},"mode":"corpse"}',
        b'{"object":{"id":"t7","created":"c"},"mode":"murder"}',
        b'{"object":{"id":"t7","created":"c"}}',
    ],
)
def test_kill_object_request_refuses_malformed_requests(data: bytes) -> None:
    with pytest.raises(WireError):
        parse_kill_object_request(data)


# --- observe ---------------------------------------------------------------


def test_observe_running_answer() -> None:
    identity = {"GC_SESSION_ID": "mc-abc", "GC_RUNTIME_EPOCH": "7"}
    answer = ObserveAnswer(state="running", box=OBJ, agent="alive", agent_pid="4242", identity=identity)
    assert json.loads(answer.encode()) == {
        "state": "running",
        "object": {"id": "t7", "created": "2026-11-09T10:00:00.123Z"},
        "agent": "alive",
        "agent_pid": "4242",
        "identity": identity,
    }


def test_observe_identity_null_and_empty_differ() -> None:
    unread = json.loads(ObserveAnswer(state="dead", box=OBJ, identity=None).encode())
    assert unread == {"state": "dead", "object": {"id": "t7", "created": OBJ.created}, "identity": None}
    foreign = json.loads(ObserveAnswer(state="dead", box=OBJ, identity={}).encode())
    assert foreign["identity"] == {}


@pytest.mark.parametrize("state", ["absent", "unknown"])
def test_observe_absent_and_unknown_carry_only_the_state(state: str) -> None:
    assert json.loads(ObserveAnswer(state=state).encode()) == {"state": state}  # type: ignore[arg-type]


def test_observe_refuses_answers_gc_would_reject() -> None:
    with pytest.raises(WireError):
        ObserveAnswer(state="running")  # a present box needs its object
    with pytest.raises(WireError):
        ObserveAnswer(state="dead", box=OBJ, agent="alive")  # contradiction
    with pytest.raises(WireError):
        ObserveAnswer(state="running", box=BoxObject(id=" ", created="c"))
    with pytest.raises(WireError):
        ObserveAnswer(state="absent", box=OBJ)


def test_identity_keys_are_the_observe_v1_four() -> None:
    assert IDENTITY_KEYS == ("GC_SESSION_ID", "GC_RUNTIME_EPOCH", "GC_INSTANCE_TOKEN", "GT_PROCESS_NAMES")


# --- inventory -------------------------------------------------------------


def test_inventory_answer_encodes_entries_and_nulls() -> None:
    answer = InventoryAnswer(
        complete=True,
        sessions=(
            InventoryEntry(
                name="mc-mayor",
                state="running",
                box=OBJ,
                agent="alive",
                attached=False,
                last_activity="2026-11-09T10:05:00.000Z",
                restart_requested=False,
                identity={"GC_SESSION_ID": "mc-1"},
            ),
            InventoryEntry(name="mc-dead", state="dead", box=BoxObject(id="t9", created="c9")),
            InventoryEntry(name="mc-unreadable"),
        ),
    )
    doc = json.loads(answer.encode())
    assert doc["complete"] is True
    first, second, third = doc["sessions"]
    assert first == {
        "name": "mc-mayor",
        "state": "running",
        "object": {"id": "t7", "created": OBJ.created},
        "agent": "alive",
        "attached": False,
        "last_activity": "2026-11-09T10:05:00.000Z",
        "restart_requested": False,
        "identity": {"GC_SESSION_ID": "mc-1"},
    }
    assert second == {
        "name": "mc-dead",
        "state": "dead",
        "object": {"id": "t9", "created": "c9"},
        "attached": None,
        "last_activity": None,
        "restart_requested": None,
        "identity": None,
    }
    assert third == {"name": "mc-unreadable"}


def test_inventory_refuses_a_repeated_name() -> None:
    entry = InventoryEntry(name="mc-a", state="dead", box=OBJ)
    with pytest.raises(WireError):
        InventoryAnswer(complete=True, sessions=(entry, entry))


@pytest.mark.parametrize("name", ["", " mc-a", "mc-a ", "mc\x07a", "mc\na"])
def test_inventory_refuses_an_unreadable_name(name: str) -> None:
    with pytest.raises(WireError):
        InventoryAnswer(complete=False, sessions=(InventoryEntry(name=name),))


def test_inventory_entry_needs_an_object_with_a_state() -> None:
    with pytest.raises(WireError):
        InventoryEntry(name="mc-a", state="running")
    with pytest.raises(WireError):
        InventoryEntry(name="mc-a", state="dead", box=OBJ, agent="alive")


# --- scalars ---------------------------------------------------------------


def test_scalars() -> None:
    assert encode_bool(True) == "true"
    assert encode_bool(False) == "false"
    assert rfc3339_ms(0) == "1970-01-01T00:00:00.000Z"
    assert rfc3339_ms(1762682400123) == "2025-11-09T10:00:00.123Z"
    with pytest.raises(ValueError):
        rfc3339_ms(-1)
    assert json.loads(WatchStartupEvent(content="Trust this folder?\n> ").encode()) == {
        "content": "Trust this folder?\n> "
    }
