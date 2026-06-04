"""Tests for the install/uninstall fragment wiring (part (a)).

The pack's discipline fragment ``use-model-advisor`` is wired into city.toml by
the *shell* lifecycle scripts (``install.sh`` / ``uninstall.sh``).  gc deprecated
the old top-level ``[workspace] global_fragments`` key in favour of
``[agent_defaults] append_fragments``; these tests pin that:

  * ``install.sh`` adds the fragment to **``[agent_defaults]`` ``append_fragments``**
    (creating the table and/or the array when absent), idempotently;
  * ``uninstall.sh`` removes it from ``append_fragments`` AND strips any legacy
    ``global_fragments`` entry an old install may have left (so an old install
    still reverses cleanly);
  * every produced city.toml round-trips through ``tomllib``.

The embedded edit logic is small Python heredocs *inside* the shell functions,
so rather than duplicate it we **extract the real functions from the shipped
scripts** and drive them.  That way a regression in the actual install/uninstall
code is caught here, with no live ``/Users/jayse/Code`` config ever touched
(everything runs on temp city.toml copies).
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

# tomllib is stdlib on 3.11+; fall back to the tomli backport if present.
try:  # pragma: no cover - import shim
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore

PACK_DIR = Path(__file__).resolve().parents[1]
INSTALL_SH = PACK_DIR / "install.sh"
UNINSTALL_SH = PACK_DIR / "uninstall.sh"
FRAG = "use-model-advisor"

pytestmark = pytest.mark.skipif(
    shutil.which("bash") is None or shutil.which("python3") is None,
    reason="needs bash + python3 to exercise the shell lifecycle helpers",
)


def _extract_fn(script: Path, name: str) -> str:
    """Return the source of shell function ``name`` from ``script``.

    Matches from the ``name() {`` line to the first line that is exactly ``}``
    (the scripts write each helper with a closing brace in column 0).
    """
    src = script.read_text()
    out, in_blk = [], False
    for line in src.splitlines():
        if re.match(r"^%s\(\)\s*\{" % re.escape(name), line):
            in_blk = True
        if in_blk:
            out.append(line)
        if in_blk and line == "}":
            break
    if not out:
        raise AssertionError(f"function {name}() not found in {script}")
    return "\n".join(out)


def _runner(*fn_sources: str):
    """Build a callable that sources the given fn sources and invokes one.

    Returns ``call(city_dir, fn, *args) -> CompletedProcess`` operating with
    ``CITY=<city_dir>`` so the extracted helpers (which reference ``$CITY``)
    resolve to the temp city.
    """
    lib = "\n\n".join(fn_sources)

    def call(city: Path, fn: str, *args: str) -> subprocess.CompletedProcess:
        script = lib + "\n" + fn + " " + " ".join(f'"{a}"' for a in args) + "\n"
        return subprocess.run(
            ["bash", "-c", script],
            env={"CITY": str(city), "PATH": _PATH},
            capture_output=True,
            text=True,
        )

    return call


# A PATH that finds python3 + bash regardless of the minimal test env.
_PATH = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"


# Extract the shipped helpers once.
_INSTALL_EDIT = _extract_fn(INSTALL_SH, "edit_fragment")
_INSTALL_PRESENT = _extract_fn(INSTALL_SH, "fragment_present")
_UNINSTALL_REMOVE = _extract_fn(UNINSTALL_SH, "edit_fragment_remove")
_UNINSTALL_PRESENT = _extract_fn(UNINSTALL_SH, "fragment_present")

_install = _runner(_INSTALL_EDIT, _INSTALL_PRESENT)
_uninstall = _runner(_UNINSTALL_REMOVE, _UNINSTALL_PRESENT)


def _city(tmp_path: Path, body: str) -> Path:
    (tmp_path / "city.toml").write_text(textwrap.dedent(body), encoding="utf-8")
    return tmp_path


def _toml(city: Path) -> dict:
    with open(city / "city.toml", "rb") as fh:
        return tomllib.load(fh)


def _append_frags(city: Path) -> list:
    return _toml(city).get("agent_defaults", {}).get("append_fragments", [])


def _legacy_frags(city: Path) -> list:
    d = _toml(city)
    # the deprecated key can sit under [workspace] or (rarely) at top level
    return d.get("workspace", {}).get("global_fragments", d.get("global_fragments", []))


# --------------------------------------------------------------------------- #
# install.sh: add to [agent_defaults] append_fragments
# --------------------------------------------------------------------------- #

def test_install_creates_agent_defaults_table_and_array(tmp_path):
    """No [agent_defaults] at all → the table + array are created."""
    city = _city(tmp_path, """
        [workspace]
        provider = "claude"

        [defaults]
        [defaults.rig]
    """)
    # not present before
    assert _install(city, "fragment_present", FRAG).returncode == 1
    r = _install(city, "edit_fragment", "add", FRAG)
    assert r.returncode == 0, r.stderr

    assert _append_frags(city) == [FRAG]
    # present after, and idempotent (byte-identical second add)
    assert _install(city, "fragment_present", FRAG).returncode == 0
    once = (city / "city.toml").read_text()
    _install(city, "edit_fragment", "add", FRAG)
    assert (city / "city.toml").read_text() == once


def test_install_inserts_array_into_existing_agent_defaults(tmp_path):
    """[agent_defaults] exists without append_fragments → the array is inserted."""
    city = _city(tmp_path, """
        [workspace]
        provider = "claude"

        [agent_defaults]
        default_sling_formula = "mol-pack-default"

        [[rigs]]
        name = "x"
    """)
    r = _install(city, "edit_fragment", "add", FRAG)
    assert r.returncode == 0, r.stderr
    d = _toml(city)
    assert d["agent_defaults"]["append_fragments"] == [FRAG]
    # sibling keys + later tables preserved (surgical edit)
    assert d["agent_defaults"]["default_sling_formula"] == "mol-pack-default"
    assert d["rigs"][0]["name"] == "x"


def test_install_appends_without_duplicating(tmp_path):
    """Existing append_fragments → ours is appended exactly once, order kept."""
    city = _city(tmp_path, """
        [workspace]
        provider = "claude"

        [agent_defaults]
        append_fragments = ["house-style"]
    """)
    _install(city, "edit_fragment", "add", FRAG)
    _install(city, "edit_fragment", "add", FRAG)  # twice
    af = _append_frags(city)
    assert af == ["house-style", FRAG]
    assert af.count(FRAG) == 1


def test_install_present_ignores_legacy_global_fragments(tmp_path):
    """A legacy global_fragments entry must NOT mask the need to add the new one.

    install-side ``fragment_present`` only consults [agent_defaults]
    append_fragments, so an old install (which wrote global_fragments) still
    triggers an add into the new home.
    """
    city = _city(tmp_path, """
        [workspace]
        provider = "claude"
        global_fragments = ["use-model-advisor"]
    """)
    # install-side presence is False (the new home is empty) → add proceeds
    assert _install(city, "fragment_present", FRAG).returncode == 1
    _install(city, "edit_fragment", "add", FRAG)
    assert _append_frags(city) == [FRAG]


# --------------------------------------------------------------------------- #
# uninstall.sh: remove from append_fragments AND strip legacy global_fragments
# --------------------------------------------------------------------------- #

def test_uninstall_removes_from_append_fragments(tmp_path):
    city = _city(tmp_path, """
        [workspace]
        provider = "claude"

        [agent_defaults]
        append_fragments = ["house-style", "use-model-advisor"]
    """)
    assert _uninstall(city, "fragment_present", FRAG).returncode == 0
    r = _uninstall(city, "edit_fragment_remove", FRAG)
    assert r.returncode == 0, r.stderr
    assert _append_frags(city) == ["house-style"]  # sibling kept
    assert _uninstall(city, "fragment_present", FRAG).returncode == 1


def test_uninstall_strips_legacy_global_fragments(tmp_path):
    """An OLD install (legacy global_fragments) still reverses cleanly."""
    city = _city(tmp_path, """
        [workspace]
        provider = "claude"
        global_fragments = ["command-glossary", "use-model-advisor"]

        [defaults]
    """)
    assert _uninstall(city, "fragment_present", FRAG).returncode == 0  # found in legacy
    _uninstall(city, "edit_fragment_remove", FRAG)
    assert _legacy_frags(city) == ["command-glossary"]
    assert _uninstall(city, "fragment_present", FRAG).returncode == 1


def test_uninstall_strips_both_homes_in_one_pass(tmp_path):
    """Legacy global_fragments AND new append_fragments both carry it → both cleaned."""
    city = _city(tmp_path, """
        [workspace]
        provider = "claude"
        global_fragments = ["command-glossary", "use-model-advisor"]

        [agent_defaults]
        append_fragments = ["house-style", "use-model-advisor"]
    """)
    _uninstall(city, "edit_fragment_remove", FRAG)
    assert _legacy_frags(city) == ["command-glossary"]
    assert _append_frags(city) == ["house-style"]
    assert _uninstall(city, "fragment_present", FRAG).returncode == 1


def test_uninstall_remove_is_idempotent(tmp_path):
    city = _city(tmp_path, """
        [agent_defaults]
        append_fragments = ["house-style"]
    """)
    before = (city / "city.toml").read_text()
    _uninstall(city, "edit_fragment_remove", FRAG)  # nothing of ours
    assert (city / "city.toml").read_text() == before


# --------------------------------------------------------------------------- #
# round-trip + parse invariants
# --------------------------------------------------------------------------- #

def test_install_then_uninstall_round_trips(tmp_path):
    """add then remove restores the array to its original (byte-identical file)."""
    city = _city(tmp_path, """
        [workspace]
        provider = "claude"

        [agent_defaults]
        append_fragments = ["house-style"]
    """)
    original = (city / "city.toml").read_text()
    _install(city, "edit_fragment", "add", FRAG)
    assert _append_frags(city) == ["house-style", FRAG]
    _uninstall(city, "edit_fragment_remove", FRAG)
    assert (city / "city.toml").read_text() == original


def test_every_edit_result_parses_as_toml(tmp_path):
    """Each produced city.toml is valid TOML (tomllib round-trips it)."""
    city = _city(tmp_path, """
        [workspace]
        provider = "claude"
    """)
    _install(city, "edit_fragment", "add", FRAG)  # creates table+array at EOF
    _toml(city)  # must not raise
    _uninstall(city, "edit_fragment_remove", FRAG)
    _toml(city)  # must not raise


def test_install_present_substring_safe(tmp_path):
    """A similarly-named fragment is not a false 'present' match."""
    city = _city(tmp_path, """
        [agent_defaults]
        append_fragments = ["use-model-advisor-extra"]
    """)
    assert _install(city, "fragment_present", FRAG).returncode == 1
