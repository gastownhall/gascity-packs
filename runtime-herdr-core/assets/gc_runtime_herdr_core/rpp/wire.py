"""Typed RPP v0 wire for what gc speaks today (gascity
``docs/reference/exec-session-provider.md``).

The handshake, the start config, observe.v1's ``observe``, ``inventory`` and
``kill-object``, ``watch-startup`` lines and the scalar answers. Shapes for
capabilities gc does not define are added together with the ops that use
them.

Readers ignore fields they do not know, so a newer gc's additions pass
through. Encoders refuse answers gc's decoders would reject (gc
``exec/observe.go``, ``exec/inventory.go``): a pack bug then fails its op
with a message saying why, instead of reaching gc as an unexplained unknown.
"""

from __future__ import annotations

import datetime
import unicodedata
from dataclasses import dataclass
from typing import Dict, Final, Literal, Mapping, Optional, Tuple

from .jsonval import JsonObject, JsonShapeError, dumps, loads

Capability = Literal[
    "observe.v1",
    "report-attachment",
    "report-activity",
    "city-scoped",
    "conformance-faults",
    "server-lifecycle",
    "fs.host",
    "carrier.ops",
    "idle-boundary",
    "input-outcome",
]
"""Tokens of gc's capability table this pack may declare (exec-session-provider.md
"Protocol Handshake"). ``proc.exec``, ``input-fence``, ``proc.provision`` and
``tty.attach`` are deliberately absent: the pack never declares them. Under
``proc.exec`` gc would send its input as tmux commands over ``exec``."""

Locality = Literal["local"]

IDENTITY_KEYS: Final = ("GC_SESSION_ID", "GC_RUNTIME_EPOCH", "GC_INSTANCE_TOKEN", "GT_PROCESS_NAMES")
"""The identity a box keeps for its life (observe.v1 rule 4)."""


class WireError(ValueError):
    """A wire document is malformed, or an answer would break gc's decoder."""


# --- handshake ---------------------------------------------------------------


@dataclass(frozen=True)
class Handshake:
    """The ``protocol`` answer: static, reading no state (exec-session-provider.md)."""

    capabilities: Tuple[Capability, ...]
    locality: Optional[Locality]

    def encode(self) -> str:
        doc: Dict[str, object] = {"version": 0, "capabilities": list(self.capabilities)}
        if self.locality is not None:
            doc["locality"] = self.locality
        return dumps(doc)


# --- start config --------------------------------------------------------------


@dataclass(frozen=True)
class CopyFile:
    """A file or directory on gc's host to stage at ``rel_dst`` under the work dir."""

    src: str
    rel_dst: str


@dataclass(frozen=True)
class StartConfig:
    """The ``start`` op's stdin (gc ``exec/json.go`` startConfig); every field is optional."""

    work_dir: str
    command: str
    lifecycle: str
    env: Mapping[str, str]
    process_names: Tuple[str, ...]
    nudge: str
    ready_prompt_prefix: str
    ready_delay_ms: int
    pre_start: Tuple[str, ...]
    session_setup: Tuple[str, ...]
    session_setup_script: str
    session_live: Tuple[str, ...]
    pack_overlay_dirs: Tuple[str, ...]
    overlay_dir: str
    copy_files: Tuple[CopyFile, ...]
    work_dir_exclude: Tuple[str, ...]
    fresh_only: bool


def parse_start_config(data: bytes) -> StartConfig:
    """Read a start config. Errors name the field, never its value."""
    try:
        doc = JsonObject.of(loads(data))
        return StartConfig(
            work_dir=doc.str_or("work_dir", ""),
            command=doc.str_or("command", ""),
            lifecycle=doc.str_or("lifecycle", ""),
            env=doc.str_map("env"),
            process_names=doc.str_tuple("process_names"),
            nudge=doc.str_or("nudge", ""),
            ready_prompt_prefix=doc.str_or("ready_prompt_prefix", ""),
            ready_delay_ms=doc.int_or("ready_delay_ms", 0),
            pre_start=doc.str_tuple("pre_start"),
            session_setup=doc.str_tuple("session_setup"),
            session_setup_script=doc.str_or("session_setup_script", ""),
            session_live=doc.str_tuple("session_live"),
            pack_overlay_dirs=doc.str_tuple("pack_overlay_dirs"),
            overlay_dir=doc.str_or("overlay_dir", ""),
            copy_files=tuple(
                CopyFile(src=entry.req_str("src"), rel_dst=entry.str_or("rel_dst", ""))
                for entry in doc.obj_tuple("copy_files")
            ),
            work_dir_exclude=doc.str_tuple("work_dir_exclude"),
            fresh_only=doc.bool_or("fresh_only", False),
        )
    except JsonShapeError as err:
        raise WireError(f"invalid start config: {err}") from None


# --- observe.v1 ------------------------------------------------------------------

ObserveState = Literal["running", "dead", "absent", "unknown"]
InventoryState = Literal["running", "dead"]
AgentState = Literal["alive", "dead", "unknown"]
KillMode = Literal["corpse", "zombie"]
KillOutcome = Literal["killed", "gone", "renamed", "live", "changed"]


@dataclass(frozen=True)
class BoxObject:
    """A box's backend identity: the same for its life, new for each new box."""

    id: str
    created: str

    def __post_init__(self) -> None:
        if not self.id.strip() or not self.created.strip():
            raise WireError("a box object needs a non-blank id and created")

    def to_json(self) -> Dict[str, object]:
        return {"id": self.id, "created": self.created}


def _identity(identity: Optional[Mapping[str, str]]) -> object:
    # null: identity not yet readable (rule 5); {}: a box with no gc identity.
    return None if identity is None else dict(identity)


@dataclass(frozen=True)
class ObserveAnswer:
    """One ``observe`` answer. ``absent`` and ``unknown`` carry only the state."""

    state: ObserveState
    box: Optional[BoxObject] = None
    agent: Optional[AgentState] = None
    agent_pid: Optional[str] = None
    identity: Optional[Mapping[str, str]] = None

    def __post_init__(self) -> None:
        present = self.state in ("running", "dead")
        if present and self.box is None:
            raise WireError(f"observe: a {self.state} box needs its object")
        if not present and (
            self.box is not None or self.agent is not None or self.agent_pid is not None or self.identity is not None
        ):
            raise WireError(f"observe: an {self.state} answer carries only its state")
        if self.state == "dead" and self.agent == "alive":
            raise WireError("observe: a dead box cannot have a live agent")

    def encode(self) -> str:
        doc: Dict[str, object] = {"state": self.state}
        if self.box is not None:
            doc["object"] = self.box.to_json()
            if self.agent is not None:
                doc["agent"] = self.agent
            if self.agent_pid is not None:
                doc["agent_pid"] = self.agent_pid
            doc["identity"] = _identity(self.identity)
        return dumps(doc)


def readable_name(name: str) -> bool:
    """A name gc can list: non-empty, untrimmed, no control character."""
    return name != "" and name == name.strip() and not any(unicodedata.category(ch) == "Cc" for ch in name)


@dataclass(frozen=True)
class InventoryEntry:
    """One listed name. Without a state it is present with unknown attributes."""

    name: str
    state: Optional[InventoryState] = None
    box: Optional[BoxObject] = None
    agent: Optional[AgentState] = None
    attached: Optional[bool] = None
    last_activity: Optional[str] = None
    restart_requested: Optional[bool] = None
    identity: Optional[Mapping[str, str]] = None

    def __post_init__(self) -> None:
        if not readable_name(self.name):
            raise WireError("inventory: a listed name must be non-empty, untrimmed and free of control characters")
        if (self.state is None) != (self.box is None):
            raise WireError("inventory: a state needs its object, and an object its state")
        if self.state is None and (
            self.agent is not None
            or self.attached is not None
            or self.last_activity is not None
            or self.restart_requested is not None
            or self.identity is not None
        ):
            raise WireError("inventory: attributes need a state")
        if self.state == "dead" and self.agent == "alive":
            raise WireError("inventory: a dead box cannot have a live agent")

    def to_json(self) -> Dict[str, object]:
        doc: Dict[str, object] = {"name": self.name}
        if self.state is None or self.box is None:
            return doc
        doc["state"] = self.state
        doc["object"] = self.box.to_json()
        if self.agent is not None:
            doc["agent"] = self.agent
        doc["attached"] = self.attached
        doc["last_activity"] = self.last_activity
        doc["restart_requested"] = self.restart_requested
        doc["identity"] = _identity(self.identity)
        return doc


@dataclass(frozen=True)
class InventoryAnswer:
    """The ``inventory`` answer; a name listed twice would fail the whole answer in gc."""

    complete: bool
    sessions: Tuple[InventoryEntry, ...]

    def __post_init__(self) -> None:
        names = [entry.name for entry in self.sessions]
        if len(set(names)) != len(names):
            raise WireError("inventory: a name is listed twice")

    def encode(self) -> str:
        return dumps({"complete": self.complete, "sessions": [entry.to_json() for entry in self.sessions]})


@dataclass(frozen=True)
class KillObjectRequest:
    """``kill-object`` stdin: kill exactly this object, re-checked by mode."""

    box: BoxObject
    mode: KillMode
    agent_pid: str


def _kill_mode(text: str) -> KillMode:
    if text == "corpse":
        return "corpse"
    if text == "zombie":
        return "zombie"
    raise WireError("invalid kill-object request: mode: expected corpse or zombie")


def parse_kill_object_request(data: bytes) -> KillObjectRequest:
    """Read a kill-object request."""
    try:
        doc = JsonObject.of(loads(data))
        target = doc.req_obj("object")
        return KillObjectRequest(
            box=BoxObject(id=target.req_str("id"), created=target.req_str("created")),
            mode=_kill_mode(doc.req_str("mode")),
            agent_pid=doc.str_or("agent_pid", ""),
        )
    except JsonShapeError as err:
        raise WireError(f"invalid kill-object request: {err}") from None


# --- scalars and streams ---------------------------------------------------------


def encode_bool(value: bool) -> str:
    """The ``true``/``false`` answer of is-running, process-alive and is-attached."""
    return "true" if value else "false"


def rfc3339_ms(epoch_ms: int) -> str:
    """Milliseconds since the epoch as RFC 3339 UTC with milliseconds."""
    if epoch_ms < 0:
        raise ValueError("epoch milliseconds must not be negative")
    seconds, millis = divmod(epoch_ms, 1000)
    stamp = datetime.datetime.fromtimestamp(seconds, datetime.timezone.utc)
    return stamp.strftime("%Y-%m-%dT%H:%M:%S") + f".{millis:03d}Z"


@dataclass(frozen=True)
class WatchStartupEvent:
    """One ``watch-startup`` NDJSON line: the screen as it now reads."""

    content: str

    def encode(self) -> str:
        return dumps({"content": self.content})
