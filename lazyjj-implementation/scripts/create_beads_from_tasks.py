#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None


PAYLOAD_RE = re.compile(
    r"^## Bead Creation Payload\s*?\n```ya?ml\s*\n(?P<body>.*?)\n```",
    re.MULTILINE | re.DOTALL,
)
CREATED_RE = re.compile(r"^## Created Beads\s*?\n.*?(?=^## |\Z)", re.MULTILINE | re.DOTALL)
FRONT_MATTER_RE = re.compile(r"\A---\n(?P<body>.*?)\n---\n", re.DOTALL)
VALID_TYPES = {"feature", "bug", "task", "chore", "docs", "test", "epic"}
VALID_PRIORITIES = {"0", "1", "2", "3", "4", "P0", "P1", "P2", "P3", "P4"}
DEFAULT_LAZYJJ_FORMULA = "mol-polecat-lazyjj-work"


class PlanError(Exception):
    pass


@dataclass
class Item:
    key: str
    title: str
    type: str
    priority: str
    description: str
    acceptance_criteria: list[str]
    dependencies: list[str] = field(default_factory=list)
    labels: list[str] = field(default_factory=list)
    files: list[str] = field(default_factory=list)
    verification: list[str] = field(default_factory=list)
    metadata: dict[str, str] = field(default_factory=dict)
    formula: str = ""
    epic: str = ""
    is_epic: bool = False


@dataclass
class Plan:
    target_rig: str
    labels: list[str]
    epics: list[Item]
    beads: list[Item]

    @property
    def items(self) -> list[Item]:
        return [*self.epics, *self.beads]


class Runner:
    def __init__(self, city: str | None, rig: str, dry_run: bool) -> None:
        self.city = city
        self.rig = rig
        self.dry_run = dry_run

    def base(self) -> list[str]:
        cmd = ["gc", "bd"]
        if self.city:
            cmd.extend(["--city", self.city])
        cmd.extend(["--rig", self.rig])
        return cmd

    def run(self, args: list[str]) -> str:
        cmd = [*self.base(), *args]
        if self.dry_run:
            print(shell_join(cmd))
            return ""
        proc = subprocess.run(cmd, text=True, capture_output=True, check=False)
        if proc.returncode != 0:
            stderr = proc.stderr.strip()
            raise PlanError(f"command failed ({proc.returncode}): {shell_join(cmd)}\n{stderr}")
        return proc.stdout


def shell_join(args: list[str]) -> str:
    import shlex

    return " ".join(shlex.quote(arg) for arg in args)


def require_yaml() -> None:
    if yaml is None:
        raise PlanError("PyYAML is required to parse tasks.md")


def extract_payload(markdown: str) -> dict[str, Any]:
    require_yaml()
    match = PAYLOAD_RE.search(markdown)
    if not match:
        raise PlanError("missing ## Bead Creation Payload fenced yaml block")
    try:
        payload = yaml.safe_load(match.group("body"))
    except Exception as exc:
        raise PlanError(f"invalid YAML payload: {exc}") from exc
    if not isinstance(payload, dict):
        raise PlanError("bead creation payload must be a YAML mapping")
    return payload


def string_list(value: Any, field_name: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise PlanError(f"{field_name} must be a list")
    out: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise PlanError(f"{field_name} must contain only non-empty strings")
        out.append(item.strip())
    return out


def metadata_map(value: Any, field_name: str) -> dict[str, str]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise PlanError(f"{field_name} must be a mapping")
    out: dict[str, str] = {}
    for key, val in value.items():
        if not isinstance(key, str) or not key.strip():
            raise PlanError(f"{field_name} keys must be non-empty strings")
        out[key.strip()] = str(val)
    return out


def parse_item(raw: Any, index: int, *, is_epic: bool) -> Item:
    name = f"{'epics' if is_epic else 'beads'}[{index}]"
    if not isinstance(raw, dict):
        raise PlanError(f"{name} must be a mapping")
    for field_name in ("key", "title", "description"):
        if not isinstance(raw.get(field_name), str) or not raw[field_name].strip():
            raise PlanError(f"{name}: missing required string field {field_name}")
    key = raw["key"].strip()
    item_type = "epic" if is_epic else str(raw.get("type", "")).strip()
    if item_type not in VALID_TYPES:
        raise PlanError(f"{key}: unsupported type {item_type!r}")
    priority = str(raw.get("priority", "2")).strip()
    if priority not in VALID_PRIORITIES:
        raise PlanError(f"{key}: priority must be 0-4 or P0-P4")
    formula = str(raw.get("formula", "")).strip()
    if not formula and not is_epic:
        formula = DEFAULT_LAZYJJ_FORMULA
    return Item(
        key=key,
        title=raw["title"].strip(),
        type=item_type,
        priority=priority,
        description=raw["description"].strip(),
        acceptance_criteria=string_list(raw.get("acceptance_criteria"), f"{key}.acceptance_criteria"),
        dependencies=string_list(raw.get("dependencies"), f"{key}.dependencies"),
        labels=string_list(raw.get("labels"), f"{key}.labels"),
        files=string_list(raw.get("files"), f"{key}.files"),
        verification=string_list(raw.get("verification"), f"{key}.verification"),
        metadata=metadata_map(raw.get("metadata"), f"{key}.metadata"),
        formula=formula,
        epic=str(raw.get("epic", "")).strip(),
        is_epic=is_epic,
    )


def parse_plan(payload: dict[str, Any]) -> Plan:
    target_rig = str(payload.get("target_rig", "")).strip()
    if not target_rig:
        raise PlanError("target_rig is required")
    raw_epics = payload.get("epics") or []
    raw_beads = payload.get("beads") or []
    if not isinstance(raw_epics, list):
        raise PlanError("epics must be a list")
    if not isinstance(raw_beads, list) or not raw_beads:
        raise PlanError("beads must be a non-empty list")
    plan = Plan(
        target_rig=target_rig,
        labels=string_list(payload.get("labels"), "labels"),
        epics=[parse_item(raw, i, is_epic=True) for i, raw in enumerate(raw_epics)],
        beads=[parse_item(raw, i, is_epic=False) for i, raw in enumerate(raw_beads)],
    )
    by_key: dict[str, Item] = {}
    for item in plan.items:
        if item.key in by_key:
            raise PlanError(f"duplicate key {item.key!r}")
        by_key[item.key] = item
    for item in plan.items:
        for dep in item.dependencies:
            if dep not in by_key:
                raise PlanError(f"{item.key}: unknown dependency {dep!r}")
        if item.epic:
            if item.epic not in by_key:
                raise PlanError(f"{item.key}: unknown epic {item.epic!r}")
            if not by_key[item.epic].is_epic:
                raise PlanError(f"{item.key}: epic {item.epic!r} is not an epic item")
    return plan


def topo_order(items: list[Item]) -> list[Item]:
    by_key = {item.key: item for item in items}
    ordered: list[Item] = []
    temporary: set[str] = set()
    permanent: set[str] = set()

    def visit(key: str) -> None:
        if key in permanent:
            return
        if key in temporary:
            raise PlanError(f"dependency cycle involving {key!r}")
        temporary.add(key)
        for dep in by_key[key].dependencies:
            visit(dep)
        temporary.remove(key)
        permanent.add(key)
        ordered.append(by_key[key])

    for item in items:
        visit(item.key)
    return ordered


def front_matter_status(markdown: str) -> str:
    require_yaml()
    match = FRONT_MATTER_RE.match(markdown)
    if not match:
        return ""
    data = yaml.load(match.group("body"), Loader=yaml.BaseLoader) or {}
    if not isinstance(data, dict):
        return ""
    return str(data.get("status", "")).strip()


def update_front_matter(markdown: str, updates: dict[str, str]) -> str:
    require_yaml()
    match = FRONT_MATTER_RE.match(markdown)
    if not match:
        return markdown
    data = yaml.load(match.group("body"), Loader=yaml.BaseLoader) or {}
    if not isinstance(data, dict):
        data = {}
    data.update(updates)
    rendered = yaml.safe_dump(data, sort_keys=False).strip()
    return f"---\n{rendered}\n---\n" + markdown[match.end() :]


def parse_created_mappings(markdown: str) -> dict[str, str]:
    match = CREATED_RE.search(markdown)
    if not match:
        return {}
    mappings: dict[str, str] = {}
    for line in match.group(0).splitlines():
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 2 or cells[0] in {"Key", "---"}:
            continue
        if cells[0] and cells[1]:
            mappings[cells[0]] = cells[1]
    return mappings


def render_created_section(items: list[Item], mappings: dict[str, str]) -> str:
    titles = {item.key: item.title for item in items}
    lines = [
        "## Created Beads",
        "",
        "| Key | Bead ID | Title |",
        "|---|---|---|",
    ]
    for key in sorted(mappings):
        lines.append(f"| {key} | {mappings[key]} | {titles.get(key, '')} |")
    return "\n".join(lines) + "\n"


def update_created_section(markdown: str, items: list[Item], mappings: dict[str, str], status: str) -> str:
    section = render_created_section(items, mappings)
    if CREATED_RE.search(markdown):
        markdown = CREATED_RE.sub(section, markdown)
    else:
        markdown = markdown.rstrip() + "\n\n" + section
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    updates = {"status": status, "updated_at": now}
    if status == "created":
        updates["created_beads_at"] = now
    return update_front_matter(markdown, updates)


def build_description(item: Item) -> str:
    parts = [item.description]
    if item.formula:
        parts.append(f"LazyJJ formula: `{item.formula}`")
    if item.files:
        parts.append("Suggested files/modules:\n" + "\n".join(f"- {path}" for path in item.files))
    if item.verification:
        parts.append("Verification:\n" + "\n".join(f"- {check}" for check in item.verification))
    return "\n\n".join(parts)


def parse_create_output(output: str) -> str:
    start = output.find("{")
    if start < 0:
        raise PlanError(f"create output did not contain JSON: {output!r}")
    data = json.loads(output[start:])
    bead_id = str(data.get("id", "")).strip()
    if not bead_id:
        raise PlanError(f"create JSON missing id: {output!r}")
    return bead_id


def create_item(runner: Runner, item: Item, plan_labels: list[str], mappings: dict[str, str]) -> str:
    if item.key in mappings:
        runner.run(["show", mappings[item.key], "--json"])
        return mappings[item.key]
    metadata = {"gc.plan.key": item.key}
    if item.formula:
        metadata["lazyjj.work_formula"] = item.formula
    metadata.update(item.metadata)
    args = [
        "create",
        "--json",
        item.title,
        "-t",
        item.type,
        "-p",
        item.priority,
        "--description",
        build_description(item),
        "--acceptance",
        "\n".join(f"- {criterion}" for criterion in item.acceptance_criteria),
        "--metadata",
        json.dumps(metadata, sort_keys=True),
    ]
    labels = [*plan_labels, *item.labels]
    if labels:
        args.extend(["--labels", ",".join(labels)])
    if item.epic and item.epic in mappings:
        args.extend(["--parent", mappings[item.epic]])
    output = runner.run(args)
    if runner.dry_run:
        return f"<{item.key}>"
    bead_id = parse_create_output(output)
    mappings[item.key] = bead_id
    return bead_id


def dependency_exists(runner: Runner, issue_id: str, depends_on_id: str) -> bool:
    output = runner.run(["dep", "list", issue_id, "--json", "--direction=up"])
    if runner.dry_run:
        return False
    try:
        deps = json.loads(output)
    except json.JSONDecodeError:
        return False
    if not isinstance(deps, list):
        return False
    return any(isinstance(dep, dict) and str(dep.get("depends_on_id", "")) == depends_on_id for dep in deps)


def add_dependencies(runner: Runner, items: list[Item], mappings: dict[str, str]) -> None:
    for item in items:
        issue_id = mappings[item.key]
        for dep_key in item.dependencies:
            depends_on_id = mappings[dep_key]
            if dependency_exists(runner, issue_id, depends_on_id):
                continue
            runner.run(["dep", "add", issue_id, depends_on_id])


def create_from_tasks(path: Path, *, city: str | None, dry_run: bool, force: bool) -> int:
    markdown = path.read_text(encoding="utf-8")
    if front_matter_status(markdown) == "created" and not force:
        raise PlanError("tasks.md already has status: created; pass --force to rerun")
    plan = parse_plan(extract_payload(markdown))
    ordered = topo_order(plan.items)
    mappings = parse_created_mappings(markdown)
    runner = Runner(city, plan.target_rig, dry_run)

    if dry_run:
        print(f"# target rig: {plan.target_rig}")
    try:
        for item in ordered:
            mappings.setdefault(item.key, create_item(runner, item, plan.labels, mappings))
        add_dependencies(runner, ordered, mappings)
    except PlanError:
        if not dry_run and mappings:
            path.write_text(update_created_section(markdown, ordered, mappings, "partial"), encoding="utf-8")
        raise

    if not dry_run:
        path.write_text(update_created_section(markdown, ordered, mappings, "created"), encoding="utf-8")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create LazyJJ-ready beads from a lazyjj-implementation.decompose tasks.md file")
    parser.add_argument("tasks_md", help="Path to tasks.md")
    parser.add_argument("--city", help="Optional city path/name passed through to gc bd")
    parser.add_argument("--dry-run", action="store_true", help="Validate and print gc bd commands without creating beads")
    parser.add_argument("--force", action="store_true", help="Allow rerun when tasks.md status is created")
    args = parser.parse_args(argv)
    try:
        return create_from_tasks(Path(args.tasks_md), city=args.city, dry_run=args.dry_run, force=args.force)
    except PlanError as exc:
        print(f"create_beads_from_tasks: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
