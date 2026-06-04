"""Outcome harvester — turn gc bead lifecycle into ``kind="quality"`` records.

This is the *read side* of the advisor reward signal (DESIGN.md §4 + §5.2). It
reads gc's bead-closure signal and emits ``kind="quality"`` invocation records to
``.beads/telemetry/invocations.jsonl``, each joined back to the ``dispatch``
record that produced the work (so the engine can credit the right
``provider::agent::shape::tier_id`` cell).

It is **read-only on gc state**: it only *reads* ``.gc/events.jsonl`` and/or
``gc bd show --json``; it never mutates a bead, runs a dispatch, or edits config.
The only thing it writes is ``quality`` lines appended to ``invocations.jsonl``.

Two input modes (DESIGN / INTEGRATION-FEASIBILITY (C)):

* **events mode** — tail ``.gc/events.jsonl`` for ``bead.closed`` (and the
  dedicated ``Reopened`` event ``bd reopen`` emits). Each event carries the full
  bead object in ``payload.bead`` (id, status, close_reason, ``metadata``,
  ``labels``, ``closed_at``), so closure quality is learnable from the stream
  alone — no extra ``bd show`` call.
* **bd-show mode** — ``gc bd show --json <id>`` for an explicit set of bead ids
  (returns a JSON *array* of bead objects). Used when you want to (re)harvest a
  specific bead rather than scan the stream.

Quality mapping (DESIGN §4):

* ``q = 1`` when the dispatched bead is **closed** and not failed
  (``status == "closed"`` and ``gc.outcome != "fail"`` and not a hard
  ``gc.failure_class``).
* ``q = 0`` on a **Reopened** event, an **escalation** state label, or a closing
  record carrying ``gc.outcome == "fail"`` / ``gc.failure_class == "hard"``.
* ``transient`` failures (rate-limit / infra) and ``blocked`` review verdicts are
  **dropped** — they don't reflect tier quality.

Channels & precedence (DESIGN §4.4): a single dispatch yields **at most one**
observation per cell, choosing the **highest-fidelity channel available**
(``eval`` > ``review`` > ``close``). Weights come from the advisor config
(``w_close=1``, ``w_review=3``, ``w_eval=5`` by default) and ride on the record
so the engine's Beta update can scale ``(a, b)`` by them.

Attribution (DESIGN §4.4): an observation attaches to the cell of the **dispatch
that produced the work**, found by joining the closed bead back to a recorded
``dispatch`` by ``bead_id`` first, then by ``session_id``
(``bead.metadata.session_id``). Quality observed on a bead whose dispatch was not
advisor-recorded is **dropped** (we can't key it to a cell).

Entry points:

* :func:`harvest` — the callable; pure-ish (I/O only on the files you pass).
* ``python -m modeladvisor.ingest`` — CLI wrapper over :func:`harvest`.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Iterable, Iterator, Mapping, Sequence

# --------------------------------------------------------------------------- #
# Config import — robust to the sibling store/engine not existing yet.         #
#                                                                              #
# ``modeladvisor/__init__.py`` eagerly imports ``modeladvisor.store`` /        #
# ``modeladvisor.engine`` (built by sibling agents). Until those land, even a  #
# plain ``import modeladvisor.config`` triggers that __init__ and raises. The  #
# harvester needs ONLY config (for channel weights + cost helpers), so we      #
# import ``modeladvisor.config`` directly without executing the package        #
# __init__: we ensure a ``modeladvisor`` parent exists in ``sys.modules``      #
# (a minimal namespace package pointing at this directory if the real one      #
# can't import), then load ``config.py`` under its true name                   #
# ``modeladvisor.config``. Loading it under its real dotted name (not an        #
# orphan alias) keeps dataclasses' type resolution happy. This degrades        #
# cleanly today and is a no-op once the siblings' modules land.                #
# --------------------------------------------------------------------------- #

SCHEMA_VERSION = "advisor.v1"


def _load_config_module():
    """Return the ``modeladvisor.config`` module, tolerating a broken __init__."""
    import importlib

    # Fast path: the package imports cleanly (siblings have landed).
    try:
        return importlib.import_module("modeladvisor.config")
    except Exception:
        pass

    # Degraded path: synthesise the parent package namespace (without running its
    # __init__) so the submodule loads under its real name.
    import importlib.util as ilu
    import types

    pkg_dir = os.path.dirname(os.path.abspath(__file__))
    pkg_name = "modeladvisor"

    if pkg_name not in sys.modules:
        parent = types.ModuleType(pkg_name)
        parent.__path__ = [pkg_dir]  # mark as a package
        parent.__package__ = pkg_name
        sys.modules[pkg_name] = parent

    mod_name = f"{pkg_name}.config"
    if mod_name in sys.modules:
        return sys.modules[mod_name]
    cfg_path = os.path.join(pkg_dir, "config.py")
    spec = ilu.spec_from_file_location(mod_name, cfg_path)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise ImportError(f"cannot load {cfg_path}")
    module = ilu.module_from_spec(spec)
    sys.modules[mod_name] = module  # register before exec so self-refs resolve
    spec.loader.exec_module(module)
    return module


_cfg_mod = _load_config_module()
AdvisorConfig = _cfg_mod.AdvisorConfig
default_config = _cfg_mod.default_config
load_config = _cfg_mod.load_config


# --------------------------------------------------------------------------- #
# Signal vocabulary                                                            #
# --------------------------------------------------------------------------- #

#: gc status that counts as a successful landing (DESIGN §4.1 / INTEGRATION (C)).
_CLOSED_STATUS = "closed"

#: Custom statuses/labels gc rigs use for the negative signal (INTEGRATION (C):
#: ``escalated``/``reopened`` are custom statuses or label-states, not built-ins).
_NEGATIVE_STATUSES = frozenset({"reopened", "escalated", "abandoned"})

#: Reviewer-verdict mapping (DESIGN §4.2). ``blocked`` is dropped (infra).
_REVIEW_PASS = frozenset({"pass", "pass_with_findings"})
_REVIEW_FAIL = frozenset({"fail"})
_REVIEW_DROP = frozenset({"blocked"})

#: Eval-verdict mapping (DESIGN §4.3). ``partial`` -> 0 (conservative).
_EVAL_PASS = frozenset({"pass"})
_EVAL_FAIL = frozenset({"fail", "partial"})

#: Channel fidelity order (DESIGN §4.4): eval > review > close. Higher wins.
_CHANNEL_FIDELITY = {"close": 1, "review": 2, "eval": 3}


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# --------------------------------------------------------------------------- #
# Join index over dispatch records                                            #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class DispatchRef:
    """The slice of a ``dispatch`` record needed to credit a cell."""

    bead_id: str
    session_id: str
    cell_key: str
    provider: str
    agent: str
    shape: str
    tier_id: str


class DispatchIndex:
    """Joins a closed bead back to the dispatch that produced it (DESIGN §4.4).

    Built by replaying the ``dispatch`` lines already in ``invocations.jsonl``.
    A bead is matched by ``bead_id`` first (the strong key, DESIGN §5.1), then by
    ``session_id`` (``bead.metadata.session_id``, INTEGRATION (C)). The most
    recent dispatch wins when several share a key (later dispatch = the live one).
    """

    def __init__(self) -> None:
        self._by_bead: dict[str, DispatchRef] = {}
        self._by_session: dict[str, DispatchRef] = {}

    def add(self, rec: Mapping[str, object]) -> None:
        if rec.get("kind") != "dispatch":
            return
        ref = DispatchRef(
            bead_id=str(rec.get("bead_id") or ""),
            session_id=str(rec.get("session_id") or ""),
            cell_key=str(rec.get("cell_key") or ""),
            provider=str(rec.get("provider") or ""),
            agent=str(rec.get("agent") or ""),
            shape=str(rec.get("shape") or ""),
            tier_id=str(rec.get("tier_id") or ""),
        )
        # Later records overwrite earlier ones (recency wins).
        if ref.bead_id:
            self._by_bead[ref.bead_id] = ref
        if ref.session_id:
            self._by_session[ref.session_id] = ref

    @classmethod
    def from_jsonl(cls, path: str | os.PathLike[str]) -> "DispatchIndex":
        idx = cls()
        for rec in _read_jsonl(path):
            idx.add(rec)
        return idx

    def lookup(self, bead_id: str, session_id: str) -> DispatchRef | None:
        if bead_id and bead_id in self._by_bead:
            return self._by_bead[bead_id]
        if session_id and session_id in self._by_session:
            return self._by_session[session_id]
        return None

    def __len__(self) -> int:  # number of joinable dispatches (by bead key)
        return len(self._by_bead) + len(self._by_session)


# --------------------------------------------------------------------------- #
# Classifying one bead's outcome into (q, channel, signal)                    #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Observation:
    """A single quality observation distilled from a bead (pre-join).

    ``q`` is a binary ``{0, 1}`` Bernoulli outcome by default (DESIGN §1.1); under
    the continuous-quality feature (DESIGN §7.3) it may instead be a graded score in
    ``[0, 1]`` (a reviewer fraction / test-pass ratio), hence the ``float`` type.
    """

    bead_id: str
    session_id: str
    q: float
    channel: str  # "close" | "review" | "eval"
    signal: str  # raw audit token
    n_dep: int = 1


def _meta_get(meta: Mapping[str, object], *keys: str) -> str:
    for k in keys:
        v = meta.get(k)
        if v is not None and str(v) != "":
            return str(v)
    return ""


def _labels_of(bead: Mapping[str, object]) -> list[str]:
    labels = bead.get("labels")
    if isinstance(labels, Sequence) and not isinstance(labels, (str, bytes)):
        return [str(x) for x in labels]
    return []


def _has_escalation(bead: Mapping[str, object], meta: Mapping[str, object]) -> bool:
    """Detect an escalation state (DESIGN §4.1 / INTEGRATION (C)).

    gc expresses escalation via ``bd set-state`` writing a ``<dim>:<val>`` label
    (e.g. ``health:failing``, ``mode:degraded``) and/or a custom ``escalated``
    status. We treat an explicit escalation label or status as ``q = 0``.
    """
    status = str(bead.get("status") or "").lower()
    if status in _NEGATIVE_STATUSES:
        return True
    for lab in _labels_of(bead):
        low = lab.lower()
        if low.startswith("escalat") or low in {"health:failing", "mode:degraded"}:
            return True
    if _meta_get(meta, "gc.final_disposition").lower() in {"escalated", "abandoned"}:
        return True
    return False


#: Metadata keys carrying a graded numeric quality score (DESIGN §7.3 continuous).
#: A fraction in [0, 1] is used directly; a 0–100 score is normalised by /100.
#: Eval-channel scores are preferred over review-channel (fidelity order, §4.4).
_EVAL_SCORE_KEYS = ("gc.eval_score", "gc.eval_fraction", "gc.test_pass_fraction")
_REVIEW_SCORE_KEYS = ("gc.review_score", "gc.score", "gc.quality_score")


def _graded_score(meta: Mapping[str, object], keys: tuple[str, ...]) -> float | None:
    """Read + normalise a graded numeric score from ``meta`` to ``[0, 1]`` (§7.3).

    A value already in ``[0, 1]`` is used as-is; a value in ``(1, 100]`` is treated
    as a percentage and divided by 100. Non-numeric / out-of-range / non-finite
    values yield ``None`` (the caller then falls back to the binary verdict).
    """
    import math as _math

    for k in keys:
        v = meta.get(k)
        if v is None or v == "":
            continue
        try:
            f = float(v)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            continue
        if not _math.isfinite(f):
            continue
        if 0.0 <= f <= 1.0:
            return f
        if 1.0 < f <= 100.0:
            return f / 100.0
    return None


def classify_bead(
    bead: Mapping[str, object],
    *,
    event_type: str | None = None,
    continuous: bool = False,
) -> Observation | None:
    """Distil a bead (+ optional event type) into one :class:`Observation`.

    Returns ``None`` when the bead carries **no** quality signal yet (e.g. still
    open with no review/eval verdict) or when the signal is explicitly *dropped*
    (``transient`` failure, ``blocked`` review). The highest-fidelity available
    channel wins (eval > review > close), per DESIGN §4.4.

    ``event_type`` lets the events-mode caller pass ``"Reopened"`` so a reopen is
    read as a negative even though the bead object may momentarily still look
    closed; ``bead.closed`` / ``bead.updated`` are treated by the bead's own
    fields.

    ``continuous`` (DESIGN §7.3, off by default): when set, a graded numeric score
    on the eval/review channel (``gc.eval_score`` / ``gc.review_score`` / a
    test-pass fraction, normalised to ``[0, 1]``) is emitted as a continuous ``q``
    instead of the binary pass/fail. Absent a graded score the binary mapping is
    used unchanged, so this is a strict superset of the v1 behaviour.
    """
    meta = bead.get("metadata")
    if not isinstance(meta, Mapping):
        meta = {}
    bead_id = str(bead.get("id") or "")
    session_id = _meta_get(meta, "session_id", "gc.session_id")
    status = str(bead.get("status") or "").lower()

    # n_dep: downstream blast radius for the loss audit (DESIGN §5.2). Best
    # effort from metadata; default 1 when unknown (DESIGN §1.3 Layer 3).
    n_dep = _coerce_int(meta.get("gc.n_dep") or meta.get("gc.dependents"), default=1)

    outcome = _meta_get(meta, "gc.outcome").lower()
    failure_class = _meta_get(meta, "gc.failure_class").lower()

    # ---- transient failures are dropped (not a quality signal, DESIGN §4.1) --
    if failure_class == "transient":
        return None

    # ---- highest fidelity: Channel C, eval verdict (DESIGN §4.3) -------------
    # Continuous (graded) eval score wins over the binary verdict when enabled.
    if continuous:
        score = _graded_score(meta, _EVAL_SCORE_KEYS)
        if score is not None:
            return Observation(bead_id, session_id, score, "eval", f"eval:score={score:.3f}", n_dep)

    eval_verdict = _meta_get(meta, "gc.eval_verdict", "gc.eval_outcome").lower()
    if eval_verdict:
        if eval_verdict in _EVAL_PASS:
            return Observation(bead_id, session_id, 1, "eval", f"eval:{eval_verdict}", n_dep)
        if eval_verdict in _EVAL_FAIL:
            return Observation(bead_id, session_id, 0, "eval", f"eval:{eval_verdict}", n_dep)
        # Unknown eval token: fall through to lower channels.

    # ---- Channel B, reviewer verdict (DESIGN §4.2) --------------------------
    # Continuous (graded) review score wins over the binary verdict when enabled.
    if continuous:
        score = _graded_score(meta, _REVIEW_SCORE_KEYS)
        if score is not None:
            return Observation(bead_id, session_id, score, "review", f"review:score={score:.3f}", n_dep)

    verdict = _meta_get(meta, "gc.verdict", "gc.review_verdict").lower()
    if verdict:
        if verdict in _REVIEW_DROP:
            return None  # blocked: infra/precondition, not a quality signal
        if verdict in _REVIEW_PASS:
            return Observation(bead_id, session_id, 1, "review", f"review:{verdict}", n_dep)
        if verdict in _REVIEW_FAIL:
            return Observation(bead_id, session_id, 0, "review", f"review:{verdict}", n_dep)
        # Unknown verdict token: fall through to closure.

    # ---- Channel A, bead closure (PRIMARY, DESIGN §4.1) ---------------------
    # Explicit reopen event => negative, regardless of the (stale) bead fields.
    if event_type and event_type.lower() in {"reopened", "bead.reopened"}:
        return Observation(bead_id, session_id, 0, "close", "reopened", n_dep)

    # Escalation state => negative.
    if _has_escalation(bead, meta):
        return Observation(bead_id, session_id, 0, "close", "escalated", n_dep)

    # Hard failure on the closing record => negative.
    if outcome == "fail" or failure_class == "hard":
        sig = "fail" if outcome == "fail" else f"failure_class:{failure_class}"
        return Observation(bead_id, session_id, 0, "close", sig, n_dep)

    # Clean close => positive.
    if status == _CLOSED_STATUS:
        # gc.outcome=pass is the cleanest success bit; a bare close (no outcome
        # metadata) is still a success per DESIGN §4.1 ("a clean close = landed").
        sig = "closed" if outcome != "pass" else "pass"
        return Observation(bead_id, session_id, 1, "close", sig, n_dep)

    # Still open / no verdict / no closure: nothing to observe yet.
    return None


def _coerce_int(value: object, *, default: int) -> int:
    try:
        if value is None or value == "":
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


# --------------------------------------------------------------------------- #
# Reading inputs                                                               #
# --------------------------------------------------------------------------- #


def _read_jsonl(path: str | os.PathLike[str]) -> Iterator[dict]:
    """Yield JSON objects from a JSONL file; skip blank/garbled lines.

    Missing file -> empty iterator (the harvester degrades to "nothing to do").
    """
    p = os.fspath(path)
    if not os.path.exists(p):
        return
    with open(p, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except (ValueError, json.JSONDecodeError):
                continue
            if isinstance(obj, dict):
                yield obj


def iter_event_beads(
    events_path: str | os.PathLike[str],
) -> Iterator[tuple[str, dict]]:
    """Yield ``(event_type, bead)`` for every closure-relevant gc event.

    Reads ``.gc/events.jsonl`` and surfaces beads from ``bead.closed``,
    ``bead.updated``, and the dedicated ``Reopened`` event (the negative signal).
    The bead object lives at ``payload.bead`` (INTEGRATION (C)); a ``Reopened``
    event may carry it at ``payload.bead`` too — we tolerate either ``payload``
    holding the bead directly or under ``bead``.
    """
    relevant = {"bead.closed", "bead.updated", "reopened", "bead.reopened"}
    for ev in _read_jsonl(events_path):
        etype = str(ev.get("type") or ev.get("event") or "").strip()
        if etype.lower() not in relevant:
            continue
        payload = ev.get("payload")
        bead: object = None
        if isinstance(payload, Mapping):
            bead = payload.get("bead", payload)
        if not isinstance(bead, Mapping) or "id" not in bead:
            continue
        yield etype, dict(bead)


def fetch_beads_via_cli(
    bead_ids: Sequence[str],
    *,
    gc_bin: str = "gc",
    cwd: str | os.PathLike[str] | None = None,
    timeout: float = 30.0,
) -> list[dict]:
    """Read beads via ``gc bd show --json <id...>`` (read-only on gc state).

    Returns the parsed bead objects (``gc bd show --json`` emits a JSON *array*).
    Any subprocess/parse failure degrades to ``[]`` so the harvester never raises
    because gc is unavailable in a given environment.
    """
    ids = [b for b in bead_ids if b]
    if not ids:
        return []
    try:
        proc = subprocess.run(
            [gc_bin, "bd", "show", "--json", *ids],
            capture_output=True,
            text=True,
            cwd=os.fspath(cwd) if cwd is not None else None,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    if proc.returncode != 0 or not proc.stdout.strip():
        return []
    try:
        data = json.loads(proc.stdout)
    except (ValueError, json.JSONDecodeError):
        return []
    if isinstance(data, Mapping):
        # Tolerate a single-object or {"beads": [...]} response shape.
        if "id" in data:
            return [dict(data)]
        inner = data.get("beads")
        return [dict(b) for b in inner if isinstance(b, Mapping)] if isinstance(inner, list) else []
    if isinstance(data, list):
        return [dict(b) for b in data if isinstance(b, Mapping)]
    return []


# --------------------------------------------------------------------------- #
# Quality-record construction + dedup/precedence                              #
# --------------------------------------------------------------------------- #


def _channel_weight(cfg: AdvisorConfig, channel: str) -> float:
    return {
        "close": cfg.hp.w_close,
        "review": cfg.hp.w_review,
        "eval": cfg.hp.w_eval,
    }.get(channel, cfg.hp.w_close)


def _build_quality_record(
    obs: Observation,
    ref: DispatchRef,
    cfg: AdvisorConfig,
    *,
    ts: str,
) -> dict:
    """Assemble a DESIGN §5.2 ``kind="quality"`` record from obs + joined cell.

    ``q`` is emitted as an ``int`` for a binary ``{0, 1}`` outcome (the v1 wire
    shape, byte-identical) and as a ``float`` only for a genuinely fractional
    graded score (DESIGN §7.3 continuous), so default telemetry is unchanged.
    """
    q_int = int(obs.q)
    q_out = q_int if float(q_int) == float(obs.q) else float(obs.q)
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": "quality",
        "ts": ts,
        "bead_id": obs.bead_id or ref.bead_id,
        "cell_key": ref.cell_key,
        "q": q_out,
        "channel": obs.channel,
        "weight": _channel_weight(cfg, obs.channel),
        "signal": obs.signal,
        "n_dep": int(obs.n_dep),
    }


def _better(a: Observation, b: Observation) -> Observation:
    """Pick the higher-fidelity observation for the same cell (DESIGN §4.4).

    Precedence: eval > review > close. On a fidelity tie, a *negative* (q=0)
    outcome wins — a failure signal is the conservative one to keep (a reopen
    after a close should not be masked by the close).
    """
    fa, fb = _CHANNEL_FIDELITY.get(a.channel, 0), _CHANNEL_FIDELITY.get(b.channel, 0)
    if fa != fb:
        return a if fa > fb else b
    if a.q != b.q:
        return a if a.q == 0 else b
    return a  # equal fidelity and outcome: keep the first


# --------------------------------------------------------------------------- #
# The harvester                                                                #
# --------------------------------------------------------------------------- #


@dataclass
class HarvestResult:
    """What :func:`harvest` produced (return value for callers + the CLI)."""

    records: list[dict] = field(default_factory=list)
    written: int = 0
    #: bead ids seen with a quality signal but no joinable dispatch (dropped).
    unjoined: list[str] = field(default_factory=list)
    #: bead ids whose signal was explicitly dropped (transient / blocked / open).
    skipped: int = 0
    out_path: str | None = None

    def __len__(self) -> int:
        return len(self.records)


def find_project_root(start: str | os.PathLike[str] | None = None) -> str | None:
    """Walk up from ``start`` (or cwd) for a directory containing ``.beads``."""
    d = os.path.abspath(os.fspath(start) if start is not None else os.getcwd())
    for _ in range(64):
        if os.path.isdir(os.path.join(d, ".beads")):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent
    return None


def harvest(
    *,
    project_root: str | os.PathLike[str] | None = None,
    invocations_path: str | os.PathLike[str] | None = None,
    events_path: str | os.PathLike[str] | None = None,
    bead_ids: Sequence[str] | None = None,
    beads: Iterable[Mapping[str, object]] | None = None,
    config: AdvisorConfig | None = None,
    config_path: str | os.PathLike[str] | None = None,
    use_cli: bool = False,
    gc_bin: str = "gc",
    write: bool = True,
    now: str | None = None,
) -> HarvestResult:
    """Harvest quality outcomes and (optionally) append ``quality`` records.

    Sources of closures, any combination of:
      * ``events_path`` — scan a gc ``events.jsonl`` for ``bead.closed`` /
        ``Reopened`` (events mode).
      * ``bead_ids`` + ``use_cli=True`` — ``gc bd show --json`` those ids
        (bd-show mode); read-only on gc.
      * ``beads`` — an explicit iterable of already-loaded bead objects
        (used by tests / callers that already have the bead JSON).

    Joining: every closure is matched back to a ``dispatch`` in
    ``invocations_path`` (defaults to ``<project_root>/.beads/telemetry/
    invocations.jsonl``) by ``bead_id`` then ``session_id``. Closures with no
    recorded dispatch are dropped and reported in
    :attr:`HarvestResult.unjoined`.

    Output: when ``write`` is true, the new ``quality`` records are **appended**
    to ``invocations_path``. The function is otherwise read-only on gc state.

    Returns a :class:`HarvestResult`.
    """
    # ---- resolve paths -----------------------------------------------------
    root = None
    if project_root is not None:
        root = os.path.abspath(os.fspath(project_root))
    elif invocations_path is None:
        root = find_project_root()

    if invocations_path is None:
        if root is None:
            raise ValueError(
                "no project_root with a .beads dir found and no invocations_path given"
            )
        invocations_path = os.path.join(root, ".beads", "telemetry", "invocations.jsonl")
    invocations_path = os.fspath(invocations_path)

    if events_path is None and root is not None:
        # Default to the city's gc stream if it exists alongside the project.
        cand = os.path.join(root, ".gc", "events.jsonl")
        if os.path.exists(cand):
            events_path = cand

    cfg = config or load_config(config_path)
    ts = now or _utcnow_iso()
    # Continuous-quality feature (DESIGN §7.3): when on, a graded numeric eval/review
    # score is emitted as a fractional q; off ⇒ binary v1 mapping (default).
    continuous = bool(getattr(cfg.hp, "continuous_quality", False))

    # ---- build the dispatch join index ------------------------------------
    index = DispatchIndex.from_jsonl(invocations_path)

    # ---- gather candidate beads (event_type, bead) ------------------------
    candidates: list[tuple[str | None, Mapping[str, object]]] = []
    if events_path is not None:
        for etype, bead in iter_event_beads(events_path):
            candidates.append((etype, bead))
    if beads is not None:
        for bead in beads:
            candidates.append((None, bead))
    if bead_ids and use_cli:
        for bead in fetch_beads_via_cli(bead_ids, gc_bin=gc_bin, cwd=root):
            candidates.append((None, bead))

    # ---- classify + collapse to one observation per cell ------------------
    # Key the dedup by the *joined* cell_key so two events on the same bead, or a
    # close-then-reopen pair, resolve to a single highest-fidelity observation
    # per cell (DESIGN §4.4 "at most one observation per cell per dispatch").
    best_by_cell: dict[str, tuple[Observation, DispatchRef]] = {}
    result = HarvestResult(out_path=invocations_path)
    unjoined_seen: set[str] = set()

    for etype, bead in candidates:
        obs = classify_bead(bead, event_type=etype, continuous=continuous)
        if obs is None:
            result.skipped += 1
            continue
        ref = index.lookup(obs.bead_id, obs.session_id)
        if ref is None or not ref.cell_key:
            # No recorded dispatch -> can't credit a cell -> drop (DESIGN §4.4).
            bid = obs.bead_id or obs.session_id
            if bid and bid not in unjoined_seen:
                unjoined_seen.add(bid)
                result.unjoined.append(bid)
            continue
        prev = best_by_cell.get(ref.cell_key)
        if prev is None:
            best_by_cell[ref.cell_key] = (obs, ref)
        else:
            best_by_cell[ref.cell_key] = (_better(prev[0], obs), ref)

    for obs, ref in best_by_cell.values():
        result.records.append(_build_quality_record(obs, ref, cfg, ts=ts))

    # Stable ordering for deterministic output/tests.
    result.records.sort(key=lambda r: (r["cell_key"], r["bead_id"]))

    # ---- append the quality records ---------------------------------------
    if write and result.records:
        os.makedirs(os.path.dirname(invocations_path), exist_ok=True)
        with open(invocations_path, "a", encoding="utf-8") as fh:
            for rec in result.records:
                fh.write(json.dumps(rec, separators=(",", ":")) + "\n")
        result.written = len(result.records)

    return result


# --------------------------------------------------------------------------- #
# CLI                                                                          #
# --------------------------------------------------------------------------- #


def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m modeladvisor.ingest",
        description=(
            "Harvest gc bead-closure outcomes into kind=quality advisor records. "
            "Read-only on gc state; appends to .beads/telemetry/invocations.jsonl."
        ),
    )
    p.add_argument(
        "--project-root",
        help="Project dir containing .beads (default: walk up from CWD).",
    )
    p.add_argument(
        "--invocations",
        help="Path to invocations.jsonl (default: <root>/.beads/telemetry/invocations.jsonl).",
    )
    p.add_argument(
        "--events",
        help="Path to a gc events.jsonl to scan (events mode). "
        "Default: <root>/.gc/events.jsonl if present.",
    )
    p.add_argument(
        "--bead",
        action="append",
        dest="bead_ids",
        metavar="ID",
        help="Bead id to harvest via `gc bd show --json` (repeatable). Implies --use-cli.",
    )
    p.add_argument(
        "--use-cli",
        action="store_true",
        help="Resolve --bead ids via `gc bd show --json` (read-only).",
    )
    p.add_argument("--gc-bin", default="gc", help="gc binary to call (default: gc).")
    p.add_argument("--config", help="Path to advisor.toml (default: built-in defaults).")
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Compute and print records without appending to invocations.jsonl.",
    )
    p.add_argument(
        "--json",
        action="store_true",
        help="Emit the produced quality records as JSON to stdout.",
    )
    return p


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    use_cli = bool(args.use_cli or args.bead_ids)
    try:
        result = harvest(
            project_root=args.project_root,
            invocations_path=args.invocations,
            events_path=args.events,
            bead_ids=args.bead_ids,
            config_path=args.config,
            use_cli=use_cli,
            gc_bin=args.gc_bin,
            write=not args.dry_run,
        )
    except ValueError as exc:
        print(f"ingest: {exc}", file=sys.stderr)
        return 2

    if args.json:
        json.dump(result.records, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        verb = "would write" if args.dry_run else "wrote"
        print(
            f"ingest: {len(result.records)} quality record(s) "
            f"({verb} {0 if args.dry_run else result.written}); "
            f"{result.skipped} skipped, {len(result.unjoined)} unjoined "
            f"-> {result.out_path}",
            file=sys.stderr,
        )
        if result.unjoined:
            print(
                "ingest: dropped (no recorded dispatch to join): "
                + ", ".join(result.unjoined),
                file=sys.stderr,
            )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
