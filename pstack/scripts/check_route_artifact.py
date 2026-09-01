#!/usr/bin/env python3
from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

PACK_ROOT = Path(__file__).resolve().parents[1]


def load_playbook_map(path: Path | None = None) -> tuple[dict[str, str], set[str], dict[str, str]]:
    data = tomllib.loads((path or PACK_ROOT / "mappings/playbooks.toml").read_text(encoding="utf-8"))
    formulas = {stem: str(entry["formula"]) for stem, entry in data["playbooks"].items()}
    classes = {stem: str(entry["class"]) for stem, entry in data["playbooks"].items()}
    unsupported = set(data["unsupported"]["stems"])
    return formulas, unsupported, classes


def check_route_front_matter(front: dict[str, Any], *, map_path: Path | None = None) -> None:
    formulas, unsupported, classes = load_playbook_map(map_path)
    status = front.get("status")
    playbook = front.get("playbook")
    formula = front.get("formula")
    route_class = front.get("class")
    if status == "unsupported":
        if playbook not in unsupported:
            raise ValueError(f"unsupported playbook not listed: {playbook}")
        if formula != "none":
            raise ValueError("unsupported route must use formula none")
        if route_class != "unsupported":
            raise ValueError("unsupported route must use class unsupported")
        return
    if status != "routed":
        raise ValueError(f"status must be routed or unsupported, got {status!r}")
    if playbook not in formulas:
        raise ValueError(f"unknown playbook: {playbook}")
    if formula != formulas[playbook]:
        raise ValueError("formula does not match playbooks.toml")
    if route_class != classes[playbook]:
        raise ValueError("class does not match playbooks.toml")
