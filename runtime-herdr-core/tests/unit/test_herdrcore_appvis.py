"""Opt-in Herdr-app labels: off by default, ``app_visibility = "labels"`` in
the city's pack config turns them on."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict

import pytest
from cityharness import City

from gc_runtime_herdr_core.herdrcore.appvis import LABEL_SPACE, LABEL_TAB, app_labels, rig_slug, space_id
from gc_runtime_herdr_core.herdrcore.config import ConfigError, read_pack_config
from gc_runtime_herdr_core.herdrcore.naming import city_label, terminal_name

CITY = "ab" * 32


def write_config(city: City, doc: object) -> None:
    ctx = city.context()
    path = os.path.join(ctx.state_dir(), "config.json")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(doc, handle)
    os.chmod(path, 0o600)


def test_no_app_labels_unless_opted_in() -> None:
    assert app_labels("off", CITY, "mayor", {"GC_RIG": "web"}) == {}


def test_app_labels_name_a_space_per_rig_and_a_tab_per_session() -> None:
    labels = app_labels("labels", CITY, "web/polecat-1", {"GC_RIG": "Web App"})
    assert labels == {LABEL_SPACE: f"gc-{city_label(CITY)}-web-app", LABEL_TAB: terminal_name(CITY, "web/polecat-1")}
    assert app_labels("labels", CITY, "boss", {})[LABEL_SPACE] == f"gc-{city_label(CITY)}"


@pytest.mark.parametrize("rig, want", [("web", "web"), ("My_Rig.v2", "my-rig-v2"), ("---", ""), ("x" * 40, "x" * 32)])
def test_rig_slugs_are_id_safe(rig: str, want: str) -> None:
    assert rig_slug(rig) == want
    assert space_id(CITY, rig).startswith("gc-")


def test_the_pack_config_validates_app_visibility(tmp_path: Path) -> None:
    (tmp_path / "config.json").write_text(json.dumps({"app_visibility": "everything"}))
    with pytest.raises(ConfigError, match="app_visibility"):
        read_pack_config(str(tmp_path))
    (tmp_path / "config.json").write_text(json.dumps({"app_visibility": "labels"}))
    assert read_pack_config(str(tmp_path)).app_visibility == "labels"
    (tmp_path / "config.json").unlink()
    assert read_pack_config(str(tmp_path)).app_visibility == "off"


def labels_of(city: City, name: str) -> Dict[str, str]:
    for record in city.terminals():
        labels = record["labels"]
        assert isinstance(labels, dict)
        if labels.get("gc.session") == name:
            return {str(k): str(v) for k, v in labels.items()}
    raise AssertionError(f"no terminal for {name}")


def test_start_writes_no_app_labels_by_default(city: City) -> None:
    assert city.start("mc-a").code == 0
    assert not any(key.startswith("herdr.") for key in labels_of(city, "mc-a"))


def test_start_writes_app_labels_when_opted_in(city: City) -> None:
    write_config(city, {"app_visibility": "labels"})
    config = '{"command":"cat","env":{"GC_RIG":"web"}}'
    assert city.start("mc-a", config).code == 0
    labels = labels_of(city, "mc-a")
    assert labels[LABEL_SPACE] == f"gc-{city_label(city.paths.city_id)}-web"
    assert labels[LABEL_TAB] == terminal_name(city.paths.city_id, "mc-a")
