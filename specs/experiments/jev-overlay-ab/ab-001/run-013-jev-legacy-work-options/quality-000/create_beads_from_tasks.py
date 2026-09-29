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
VALID_TYPES = {"feature", "bug", "task", "chore", "docs"}
VALID_PRIORITIES = {"0", "1", "2", "3", "4", "P0", "P1", "P2", "P3", "P4"}


class PlanError(Exception):
    pass


@dataclass
class Runnable:
    key: str
    title: str
    type: str
    priority: str
    description: str
    acceptance_criteria: list[str]
    parent_convoy: str
    dependencies: list[str] = field(default_factory=list)
    labels: list[str] = field(default_factory=list)
    files: list[str] = field(default_factory=list)
    verification: list[str] = field(default_factory=list)
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass
class Convoy:
    key: str
    title: str
    description: str
    parent_convoy: str = ""
    dependencies: list[str] = field(default_factory=list)
    labels: list[str] = field(default_factory=list)
    metadata: dict[str, str] = field(default_factory=dict)
    target: str = ""
    convoy_keys: list[str] = field(default_factory=list)
    bead_keys: list[str] = field(default_factory=list)


@dataclass
class Plan:
    target_rig: str
    labels: list[str]
    convoys: list[Convoy]
    runnables: list[Runnable]

    @property
    def items(self) -> list[Convoy | Runnable]:
        return [*self.convoys, *self.runnables]


class Runner:
    def __init__(self, city: str | None, rig: str, dry_run: bool) -> None:
        self.city = city
        self.rig = rig
        self.dry_run = dry_run
        self.seeded_convoy_members: dict[str, str] = {}

    def bd_base(self) -> list[str]:
        cmd = ["gc", "bd"]
        if self.city:
            cmd.extend(["--city", self.city])
        cmd.extend(["--rig", self.rig])
        return cmd

    def convoy_base(self) -> list[str]:
        cmd = ["gc", "convoy"]
        if self.city:
            cmd.extend(["--city", self.city])
        cmd.extend(["--rig", self.rig])
        return cmd

    def run_bd(self, args: list[str]) -> str:
        return self.run([*self.bd_base(), *args])

    def run_convoy(self, args: list[str]) -> str:
        return self.run([*self.convoy_base(), *args])

    def run(self, cmd: list[str]) -> str:
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


def required_string(raw: dict[str, Any], field_name: str, item_name: str) -> str:
    value = raw.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise PlanError(f"{item_name}: missing required string field {field_name}")
    return value.strip()


def parse_runnable(
    raw: Any,
    index: int,
    *,
    parent_convoy: str,
    inherited_labels: list[str],
    inherited_metadata: dict[str, str],
) -> Runnable:
    name = f"beads[{index}]"
    if not isinstance(raw, dict):
        raise PlanError(f"{name} must be a mapping")
    key = required_string(raw, "key", name)
    item_type = str(raw.get("type", "")).strip()
    if item_type not in VALID_TYPES:
        raise PlanError(f"{key}: unsupported type {item_type!r}")
    priority = str(raw.get("priority", "2")).strip()
    if priority not in VALID_PRIORITIES:
        raise PlanError(f"{key}: priority must be 0-4 or P0-P4")
    metadata = {**inherited_metadata, **metadata_map(raw.get("metadata"), f"{key}.metadata")}
    return Runnable(
        key=key,
        title=required_string(raw, "title", key),
        type=item_type,
        priority=priority,
        description=required_string(raw, "description", key),
        acceptance_criteria=string_list(raw.get("acceptance_criteria"), f"{key}.acceptance_criteria"),
        parent_convoy=parent_convoy,
        dependencies=string_list(raw.get("dependencies"), f"{key}.dependencies"),
        labels=[*inherited_labels, *string_list(raw.get("labels"), f"{key}.labels")],
        files=string_list(raw.get("files"), f"{key}.files"),
        verification=string_list(raw.get("verification"), f"{key}.verification"),
        metadata=metadata,
    )


def parse_convoy(
    raw: Any,
    index: int,
    *,
    parent_convoy: str,
    plan: Plan,
    inherited_labels: list[str],
    inherited_metadata: dict[str, str],
    inherited_target: str,
) -> None:
    name = f"convoys[{index}]"
    if not isinstance(raw, dict):
        raise PlanError(f"{name} must be a mapping")
    key = required_string(raw, "key", name)
    labels = [*inherited_labels, *string_list(raw.get("labels"), f"{key}.labels")]
    metadata = {**inherited_metadata, **metadata_map(raw.get("metadata"), f"{key}.metadata")}
    target = str(raw.get("target", inherited_target)).strip()
    convoy = Convoy(
        key=key,
        title=required_string(raw, "title", key),
        description=required_string(raw, "description", key),
        parent_convoy=parent_convoy,
        dependencies=string_list(raw.get("dependencies"), f"{key}.dependencies"),
        labels=labels,
        metadata=metadata,
        target=target,
    )
    plan.convoys.append(convoy)

    for child_index, child in enumerate(raw.get("convoys") or []):
        if not isinstance(child, dict):
            raise PlanError(f"{key}.convoys[{child_index}] must be a mapping")
        child_key = required_string(child, "key", f"{key}.convoys[{child_index}]")
        parse_convoy(
            child,
            child_index,
            parent_convoy=key,
            plan=plan,
            inherited_labels=labels,
            inherited_metadata=metadata,
            inherited_target=target,
        )
        convoy.convoy_keys.append(child_key)

    raw_beads = raw.get("beads") or []
    if not isinstance(raw_beads, list):
        raise PlanError(f"{key}.beads must be a list")
    for bead_index, bead in enumerate(raw_beads):
        runnable = parse_runnable(
            bead,
            bead_index,
            parent_convoy=key,
            inherited_labels=labels,
            inherited_metadata=metadata,
        )
        plan.runnables.append(runnable)
        convoy.bead_keys.append(runnable.key)


def parse_plan(payload: dict[str, Any]) -> Plan:
    target_rig = str(payload.get("target_rig", "")).strip()
    if not target_rig:
        raise PlanError("target_rig is required")
    if "epics" in payload:
        raise PlanError("epics[] is not supported; use nested convoys[]")
    raw_convoys = payload.get("convoys") or []
    raw_beads = payload.get("beads") or []
    if not isinstance(raw_convoys, list):
        raise PlanError("convoys must be a list")
    if not isinstance(raw_beads, list):
        raise PlanError("beads must be a list")
    plan = Plan(target_rig=target_rig, labels=string_list(payload.get("labels"), "labels"), convoys=[], runnables=[])
    for index, raw in enumerate(raw_convoys):
        parse_convoy(
            raw,
            index,
            parent_convoy="",
            plan=plan,
            inherited_labels=plan.labels,
            inherited_metadata={},
            inherited_target="",
        )
    for index, raw in enumerate(raw_beads):
        plan.runnables.append(
            parse_runnable(
                raw,
                index,
                parent_convoy="",
                inherited_labels=plan.labels,
                inherited_metadata={},
            )
        )
    if not plan.runnables:
        raise PlanError("beads must contain at least one runnable item, directly or inside convoys")
    validate_plan(plan)
    return plan


def validate_plan(plan: Plan) -> None:
    by_key: dict[str, Convoy | Runnable] = {}
    for item in plan.items:
        if item.key in by_key:
            raise PlanError(f"duplicate key {item.key!r}")
        by_key[item.key] = item
    for item in plan.items:
        for dep in item.dependencies:
            if dep not in by_key:
                raise PlanError(f"{item.key}: unknown dependency {dep!r}")
    for convoy in plan.convoys:
        if not convoy.convoy_keys and not convoy.bead_keys:
            raise PlanError(f"{convoy.key}: convoy must contain at least one bead or nested convoy")
    topo_order(plan.runnables, expanded_dependency_edges(plan))


def descendants(plan: Plan, convoy_key: str) -> set[str]:
    result: set[str] = set()
    for convoy in plan.convoys:
        if convoy.parent_convoy == convoy_key:
            result.add(convoy.key)
            result.update(descendants(plan, convoy.key))
    for runnable in plan.runnables:
        if runnable.parent_convoy == convoy_key:
            result.add(runnable.key)
    return result


def runnable_descendants(plan: Plan, key: str) -> list[str]:
    item = item_map(plan)[key]
    if isinstance(item, Runnable):
        return [key]
    nested = descendants(plan, key)
    return [runnable.key for runnable in plan.runnables if runnable.key in nested]


def root_runnables(plan: Plan, key: str) -> list[str]:
    runnable_keys = set(runnable_descendants(plan, key))
    edges = explicit_runnable_edges(plan)
    blocked = {child for child, dep in edges if child in runnable_keys and dep in runnable_keys}
    return [runnable.key for runnable in plan.runnables if runnable.key in runnable_keys and runnable.key not in blocked]


def terminal_runnables(plan: Plan, key: str) -> list[str]:
    runnable_keys = set(runnable_descendants(plan, key))
    edges = explicit_runnable_edges(plan)
    predecessors = {dep for child, dep in edges if child in runnable_keys and dep in runnable_keys}
    return [runnable.key for runnable in plan.runnables if runnable.key in runnable_keys and runnable.key not in predecessors]


def item_map(plan: Plan) -> dict[str, Convoy | Runnable]:
    return {item.key: item for item in plan.items}


def explicit_runnable_edges(plan: Plan) -> set[tuple[str, str]]:
    by_key = item_map(plan)
    edges: set[tuple[str, str]] = set()
    for runnable in plan.runnables:
        for dep in runnable.dependencies:
            dep_item = by_key[dep]
            if isinstance(dep_item, Runnable):
                edges.add((runnable.key, dep))
    return edges


def expanded_dependency_edges(plan: Plan) -> set[tuple[str, str]]:
    by_key = item_map(plan)
    edges = explicit_runnable_edges(plan)

    def add_expanded(dependent_key: str, dependency_key: str) -> None:
        dependent = by_key[dependent_key]
        dependency = by_key[dependency_key]
        dependent_roots = [dependent.key] if isinstance(dependent, Runnable) else root_runnables(plan, dependent.key)
        dependency_terms = [dependency.key] if isinstance(dependency, Runnable) else terminal_runnables(plan, dependency.key)
        for child in dependent_roots:
            for dep in dependency_terms:
                if child != dep:
                    edges.add((child, dep))

    for item in plan.items:
        for dep in item.dependencies:
            add_expanded(item.key, dep)
    return edges


def topo_order(items: list[Runnable], edges: set[tuple[str, str]] | None = None) -> list[Runnable]:
    by_key = {item.key: item for item in items}
    ordered: list[Runnable] = []
    temporary: set[str] = set()
    permanent: set[str] = set()
    edges = edges or explicit_edges_for_items(items)

    def visit(key: str) -> None:
        if key in permanent:
            return
        if key in temporary:
            raise PlanError(f"dependency cycle involving {key!r}")
        temporary.add(key)
        for child, dep in sorted(edges):
            if child == key and dep in by_key:
                visit(dep)
        temporary.remove(key)
        permanent.add(key)
        ordered.append(by_key[key])

    for item in items:
        visit(item.key)
    return ordered


def explicit_edges_for_items(items: list[Runnable]) -> set[tuple[str, str]]:
    keys = {item.key for item in items}
    return {(item.key, dep) for item in items for dep in item.dependencies if dep in keys}


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
        if len(cells) >= 4 and cells[0] and cells[2]:
            mappings[cells[0]] = cells[2]
        elif len(cells) >= 2 and cells[0] and cells[1]:
            mappings[cells[0]] = cells[1]
    return mappings


def render_created_section(plan: Plan, mappings: dict[str, str]) -> str:
    titles = {item.key: item.title for item in plan.items}
    kinds = {convoy.key: "convoy" for convoy in plan.convoys}
    kinds.update({runnable.key: "bead" for runnable in plan.runnables})
    ordered_keys = [item.key for item in [*plan.convoys, *plan.runnables] if item.key in mappings]
    lines = [
        "## Created Beads",
        "",
        "| Key | Kind | Bead ID | Title |",
        "|---|---|---|---|",
    ]
    for key in ordered_keys:
        lines.append(f"| {key} | {kinds[key]} | {mappings[key]} | {titles.get(key, '')} |")
    return "\n".join(lines) + "\n"


def update_created_section(markdown: str, plan: Plan, mappings: dict[str, str], status: str) -> str:
    section = render_created_section(plan, mappings)
    if CREATED_RE.search(markdown):
        markdown = CREATED_RE.sub(section, markdown)
    else:
        markdown = markdown.rstrip() + "\n\n" + section
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    updates = {"status": status, "updated_at": now}
    if status == "created":
        updates["created_beads_at"] = now
    return update_front_matter(markdown, updates)


def build_description(item: Runnable) -> str:
    parts = [item.description]
    if item.files:
        parts.append("Suggested files/modules:\n" + "\n".join(f"- {path}" for path in item.files))
    if item.verification:
        parts.append("Verification:\n" + "\n".join(f"- {check}" for check in item.verification))
    return "\n\n".join(parts)


def parse_create_output(output: str) -> str:
    start = output.find("{")
    if start < 0:
        raise PlanError(f"create output did not contain JSON: {output!r}")
    try:
        data, _ = json.JSONDecoder().raw_decode(output[start:])
    except json.JSONDecodeError as exc:
        raise PlanError(f"create output did not contain valid JSON: {output!r}") from exc
    if not isinstance(data, dict):
        raise PlanError(f"create JSON was not an object: {output!r}")
    bead_id = str(data.get("id") or data.get("bead_id") or data.get("convoy_id") or "").strip()
    if not bead_id:
        raise PlanError(f"create JSON missing id: {output!r}")
    return bead_id


def create_runnable(runner: Runner, item: Runnable, mappings: dict[str, str]) -> str:
    if item.key in mappings:
        runner.run_bd(["show", mappings[item.key], "--json"])
        return mappings[item.key]
    metadata = {"gc.plan.key": item.key, "gc.plan.kind": "bead"}
    if item.parent_convoy:
        metadata["gc.plan.parent_convoy"] = item.parent_convoy
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
    if item.labels:
        args.extend(["--labels", ",".join(dict.fromkeys(item.labels))])
    output = runner.run_bd(args)
    if runner.dry_run:
        return f"<{item.key}>"
    bead_id = parse_create_output(output)
    mappings[item.key] = bead_id
    return bead_id


def create_convoy(runner: Runner, convoy: Convoy, mappings: dict[str, str]) -> str:
    member_keys = [*convoy.convoy_keys, *convoy.bead_keys]
    if convoy.key in mappings:
        runner.run_bd(["show", mappings[convoy.key], "--json"])
        if member_keys:
            runner.seeded_convoy_members[convoy.key] = member_keys[0]
        update_convoy_metadata(runner, convoy, mappings[convoy.key])
        return mappings[convoy.key]
    if not member_keys:
        raise PlanError(f"{convoy.key}: convoy must contain at least one bead or nested convoy")
    args = ["create", "--json"]
    if convoy.target:
        args.extend(["--target", convoy.target])
    args.append(convoy.title)
    seed_key = member_keys[0]
    args.append(mappings[seed_key])
    output = runner.run_convoy(args)
    convoy_id = f"<{convoy.key}>" if runner.dry_run else parse_create_output(output)
    mappings[convoy.key] = convoy_id
    runner.seeded_convoy_members[convoy.key] = seed_key
    update_convoy_metadata(runner, convoy, convoy_id)
    return convoy_id


def update_convoy_metadata(runner: Runner, convoy: Convoy, convoy_id: str) -> None:
    metadata = {
        "gc.plan.key": convoy.key,
        "gc.plan.kind": "convoy",
        **convoy.metadata,
    }
    if convoy.parent_convoy:
        metadata["gc.plan.parent_convoy"] = convoy.parent_convoy
    runner.run_bd(["update", convoy_id, "--metadata", json.dumps(metadata, sort_keys=True)])


def link_memberships(runner: Runner, plan: Plan, mappings: dict[str, str]) -> None:
    for convoy in plan.convoys:
        convoy_id = mappings[convoy.key]
        seeded_key = runner.seeded_convoy_members.get(convoy.key)
        existing_member_ids = existing_convoy_members(runner, convoy_id)
        for key in [*convoy.convoy_keys, *convoy.bead_keys]:
            if key == seeded_key:
                continue
            member_id = mappings[key]
            if member_id in existing_member_ids:
                continue
            runner.run_convoy(["add", convoy_id, member_id])
            existing_member_ids.add(member_id)


def existing_convoy_members(runner: Runner, convoy_id: str) -> set[str]:
    if runner.dry_run:
        return set()
    output = runner.run_bd(["dep", "list", convoy_id, "--type", "tracks", "--json"])
    try:
        deps = json.loads(output)
    except json.JSONDecodeError:
        return set()
    if not isinstance(deps, list):
        return set()
    member_ids: set[str] = set()
    for dep in deps:
        if not isinstance(dep, dict):
            continue
        dep_type = str(dep.get("type") or dep.get("dependency_type") or "").strip()
        if dep_type and dep_type != "tracks":
            continue
        dep_id = str(dep.get("depends_on_id") or "").strip()
        if not dep_id:
            dep_id = str(dep.get("target_id") or dep.get("to_id") or dep.get("issue_id") or dep.get("id") or "").strip()
        if dep_id:
            member_ids.add(dep_id)
    return member_ids


def dependency_exists(runner: Runner, issue_id: str, depends_on_id: str) -> bool:
    output = runner.run_bd(["dep", "list", issue_id, "--json"])
    if runner.dry_run:
        return False
    try:
        deps = json.loads(output)
    except json.JSONDecodeError:
        return False
    if not isinstance(deps, list):
        return False
    for dep in deps:
        if not isinstance(dep, dict):
            continue
        dep_id = str(dep.get("depends_on_id") or dep.get("id") or "").strip()
        dep_type = str(dep.get("type") or dep.get("dependency_type") or "blocks").strip()
        if dep_id == depends_on_id and dep_type == "blocks":
            return True
    return False


def add_dependencies(runner: Runner, plan: Plan, mappings: dict[str, str]) -> None:
    for child_key, dep_key in sorted(expanded_dependency_edges(plan)):
        issue_id = mappings[child_key]
        depends_on_id = mappings[dep_key]
        if dependency_exists(runner, issue_id, depends_on_id):
            continue
        runner.run_bd(["dep", "add", issue_id, depends_on_id])


def create_from_tasks(path: Path, *, city: str | None, dry_run: bool, force: bool) -> int:
    markdown = path.read_text(encoding="utf-8")
    if front_matter_status(markdown) == "created" and not force:
        raise PlanError("tasks.md already has status: created; pass --force to rerun")
    plan = parse_plan(extract_payload(markdown))
    ordered_runnables = topo_order(plan.runnables, expanded_dependency_edges(plan))
    mappings = parse_created_mappings(markdown)
    runner = Runner(city, plan.target_rig, dry_run)

    if dry_run:
        print(f"# target rig: {plan.target_rig}")
    try:
        for item in ordered_runnables:
            mappings.setdefault(item.key, create_runnable(runner, item, mappings))
        for convoy in reversed(plan.convoys):
            mappings.setdefault(convoy.key, create_convoy(runner, convoy, mappings))
        link_memberships(runner, plan, mappings)
        add_dependencies(runner, plan, mappings)
    except PlanError:
        if not dry_run and mappings:
            path.write_text(update_created_section(markdown, plan, mappings, "partial"), encoding="utf-8")
        raise

    if not dry_run:
        path.write_text(update_created_section(markdown, plan, mappings, "created"), encoding="utf-8")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create Gas City beads and convoys from a gc mayor tasks.md file")
    parser.add_argument("tasks_md", help="Path to tasks.md")
    parser.add_argument("--city", help="Optional city path/name passed through to gc")
    parser.add_argument("--dry-run", action="store_true", help="Validate and print gc commands without creating beads")
    parser.add_argument("--force", action="store_true", help="Allow rerun when tasks.md status is created")
    args = parser.parse_args(argv)
    try:
        return create_from_tasks(Path(args.tasks_md), city=args.city, dry_run=args.dry_run, force=args.force)
    except PlanError as exc:
        print(f"create_beads_from_tasks: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
