from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import pathlib
import tomllib
import unittest


PACK_ROOT = pathlib.Path(__file__).resolve().parents[1]
REPO_ROOT = PACK_ROOT.parent
CONTRACT_ROOT = PACK_ROOT / "schemas" / "workspace"
FIXTURE_ROOT = PACK_ROOT / "tests" / "fixtures" / "workspace-records"
SUPPORTED_PACKS = {"gascity", "compound-engineering", "superpowers", "bmad", "gstack"}


def records_module():
    path = PACK_ROOT / "assets" / "scripts" / "workspace_records.py"
    spec = importlib.util.spec_from_file_location("workspace_records", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fixture_records():
    return json.loads((FIXTURE_ROOT / "valid.json").read_text(encoding="utf-8"))


class WorkspaceRecordTests(unittest.TestCase):
    def test_schema_bundle_validates_records_without_the_helper(self):
        module = records_module()
        module.jsonschema.Draft202012Validator.check_schema(module.schema_bundle())
        validator = module.jsonschema.Draft202012Validator(module.schema_bundle())
        for kind, record in fixture_records().items():
            with self.subTest(kind=kind):
                validator.validate(record)
                invalid = dict(record, version=2)
                with self.assertRaises(module.jsonschema.ValidationError):
                    validator.validate(invalid)

    def test_valid_records_have_closed_versioned_contracts(self):
        module = records_module()
        records = fixture_records()
        self.assertEqual(set(records), set(module.contracts()))
        for kind, record in records.items():
            with self.subTest(kind=kind):
                self.assertEqual(module.validate_record(kind, record), record)
                self.assertTrue(module.record_identity(kind, record))

    def test_each_required_field_and_version_is_enforced(self):
        module = records_module()
        for kind, record in fixture_records().items():
            contract = module.contracts()[kind]
            schema = module.record_schema(kind)
            self.assertIn("version", schema["required"])
            self.assertIn("workflow_root_id", contract["identity"])
            self.assertIn("generation", contract["identity"])
            for field in schema["required"]:
                invalid = copy.deepcopy(record)
                del invalid[field]
                with self.subTest(kind=kind, missing=field):
                    with self.assertRaises(module.RecordError):
                        module.validate_record(kind, invalid)
            for invalid_version in (0, 2, "1", True, None):
                invalid = copy.deepcopy(record)
                invalid["version"] = invalid_version
                with self.subTest(kind=kind, version=invalid_version):
                    with self.assertRaises(module.RecordError):
                        module.validate_record(kind, invalid)

    def test_negative_fixtures_fail_closed(self):
        module = records_module()
        fixtures = json.loads((FIXTURE_ROOT / "invalid.json").read_text(encoding="utf-8"))
        for case in fixtures:
            with self.subTest(case=case["name"]):
                with self.assertRaisesRegex(module.RecordError, case["error"]):
                    module.validate_record(case["kind"], case["record"])

    def test_conflicting_replay_fixtures_fail_closed(self):
        module = records_module()
        fixtures = json.loads((FIXTURE_ROOT / "conflicting-replay.json").read_text(encoding="utf-8"))
        for case in fixtures:
            with self.subTest(case=case["name"]):
                with self.assertRaisesRegex(module.RecordError, case["error"]):
                    module.verify_replay(case["kind"], case["stored"], case["candidate"])

    def test_canonical_bytes_ignore_object_order_and_preserve_array_order(self):
        module = records_module()
        record = fixture_records()["source-plan"]
        reversed_keys = dict(reversed(list(record.items())))
        self.assertEqual(module.canonical_bytes(record), module.canonical_bytes(reversed_keys))
        self.assertEqual(module.record_sha256(record), hashlib.sha256(module.canonical_bytes(record)).hexdigest())
        reordered = copy.deepcopy(record)
        reordered["nodes"].reverse()
        self.assertNotEqual(module.canonical_bytes(record), module.canonical_bytes(reordered))
        self.assertNotIn(b"\n", module.canonical_bytes(record))
        with self.assertRaises(module.RecordError):
            module.canonical_bytes({"version": float("nan")})

    def test_exact_replay_succeeds_and_changed_payload_conflicts(self):
        module = records_module()
        for kind, record in fixture_records().items():
            with self.subTest(kind=kind):
                self.assertTrue(module.verify_replay(kind, record, dict(reversed(list(record.items())))))
                changed = copy.deepcopy(record)
                changed["writer_step_id"] += "-other"
                if kind == "workspace":
                    changed["claim_binding"]["writer_step_id"] = changed["writer_step_id"]
                with self.assertRaisesRegex(module.RecordError, "conflicting replay"):
                    module.verify_replay(kind, record, changed)

    def test_cross_run_and_generation_replays_are_identity_conflicts(self):
        module = records_module()
        for kind, record in fixture_records().items():
            for field, value in (("workflow_root_id", "other-run"), ("generation", record["generation"] + 1)):
                changed = copy.deepcopy(record)
                changed[field] = value
                if kind == "workspace":
                    changed["claim_binding"][field] = value
                with self.subTest(kind=kind, field=field):
                    with self.assertRaisesRegex(module.RecordError, "identity conflict|generation"):
                        module.verify_replay(kind, record, changed)

    def test_lookup_uses_an_explicit_physical_id_and_rejects_ambiguity(self):
        module = records_module()
        record = fixture_records()["workspace"]
        identity = list(module.record_identity("workspace", record))
        reference = {"kind": "workspace", "identity": identity, "bead_id": record["workspace_bead_id"]}
        self.assertEqual(module.resolve_record_id("workspace", record, [reference]), reference["bead_id"])
        self.assertNotEqual(reference["bead_id"], record["workspace_owner_id"] + ".gc-ws")
        with self.assertRaisesRegex(module.RecordError, "missing record reference"):
            module.resolve_record_id("workspace", record, [])
        other = dict(reference, bead_id="fixture-other-workspace")
        with self.assertRaisesRegex(module.RecordError, "ambiguous record reference"):
            module.resolve_record_id("workspace", record, [reference, other])
        with self.assertRaisesRegex(module.RecordError, "physical workspace"):
            module.resolve_record_id("workspace", record, [other])
        with self.assertRaisesRegex(module.RecordError, "record reference"):
            module.resolve_record_id("workspace", record, [None])

    def test_no_change_and_acceptance_are_separate_from_completion(self):
        module = records_module()
        record = fixture_records()["member-result"]
        no_change = copy.deepcopy(record)
        no_change.update(status="no_change", output_oid=record["input_oid"], commit_oids=[])
        no_change["acceptance"]["subject_oid"] = no_change["output_oid"]
        self.assertEqual(module.validate_record("member-result", no_change)["status"], "no_change")
        self.assertEqual(no_change["acceptance"]["status"], "unverified")
        invalid = dict(no_change, output_oid="c" * 40)
        with self.assertRaisesRegex(module.RecordError, "no_change"):
            module.validate_record("member-result", invalid)
        invalid = copy.deepcopy(record)
        invalid["acceptance"]["status"] = "accepted"
        with self.assertRaisesRegex(module.RecordError, "accepted"):
            module.validate_record("member-result", invalid)

    def test_accepted_checks_bind_the_exact_output(self):
        module = records_module()
        record = fixture_records()["member-result"]
        record["acceptance"] = {
            "status": "accepted", "subject_oid": record["output_oid"], "artifacts": [],
            "project_checks": [{"command": "example-project-check", "subject_oid": record["output_oid"], "exit_code": 0,
                                "evidence_path": "/example/artifacts/check.txt", "evidence_sha256": "0" * 64}],
            "independent_review": {"status": "passed", "reviewed_oid": record["output_oid"], "reviewer": "independent-reviewer-example",
                                   "report_path": "/example/artifacts/review.md", "report_sha256": "0" * 64},
        }
        self.assertEqual(module.validate_record("member-result", record)["acceptance"]["status"], "accepted")
        record["acceptance"]["project_checks"][0]["subject_oid"] = record["input_oid"]
        with self.assertRaisesRegex(module.RecordError, "accepted"):
            module.validate_record("member-result", record)
        record["acceptance"]["project_checks"][0]["subject_oid"] = record["output_oid"]
        record["acceptance"]["independent_review"]["reviewer"] = record["writer_step_id"]
        with self.assertRaisesRegex(module.RecordError, "accepted"):
            module.validate_record("member-result", record)

    def test_workspace_claim_binding_retains_stable_owner(self):
        module = records_module()
        record = fixture_records()["workspace"]
        self.assertNotEqual(record["writer_attempt_id"], record["native_attempt_id"])
        self.assertNotEqual(record["writer_step_id"], record["workspace_owner_id"])
        record["claim_binding"]["workspace_owner_id"] = record["writer_step_id"]
        with self.assertRaisesRegex(module.RecordError, "claim binding"):
            module.validate_record("workspace", record)

    def test_workspace_claim_binding_binds_exact_writer_attempt(self):
        module = records_module()
        record = fixture_records()["workspace"]
        for field in ("writer_step_id", "writer_attempt_id"):
            invalid = copy.deepcopy(record)
            invalid["claim_binding"][field] = "other-writer"
            with self.subTest(field=field):
                with self.assertRaisesRegex(module.RecordError, "claim binding"):
                    module.validate_record("workspace", invalid)

    def test_workspace_can_represent_detached_without_claiming_native_support(self):
        module = records_module()
        record = fixture_records()["workspace"]
        record["work_branch"] = None
        record["native_provenance"]["mode"] = "detached"
        record["native_provenance"]["extension-example"] = {"preserve": True}
        module.validate_record("workspace", record)
        self.assertEqual(record["native_provenance"]["extension-example"], {"preserve": True})

    def test_observed_publication_binds_intended_output(self):
        module = records_module()
        record = fixture_records()["publish"]
        record.update(status="observed", observed_oid=record["output_oid"])
        module.validate_record("publish", record)
        record["observed_oid"] = "f" * 40
        with self.assertRaisesRegex(module.RecordError, "observed_oid"):
            module.validate_record("publish", record)

    def test_unknown_fields_kinds_and_duplicate_json_keys_are_rejected(self):
        module = records_module()
        record = fixture_records()["run"]
        with self.assertRaises(module.RecordError):
            module.validate_record("run", dict(record, ambient_head="a" * 40))
        with self.assertRaisesRegex(module.RecordError, "unknown record kind"):
            module.validate_record("future-record", record)
        with self.assertRaisesRegex(module.RecordError, "duplicate JSON key"):
            module.parse_record('{"version": 1, "version": 2}')

    def test_shared_patterns_refuse_terminal_newlines_and_path_controls(self):
        module = records_module()
        records = fixture_records()
        for kind, field in (("run", "workflow_root_id"), ("run", "base_oid"),
                            ("canonical", "summary_sha256"), ("publish", "pr_url")):
            invalid = copy.deepcopy(records[kind])
            invalid[field] = (invalid[field] or "https://example.invalid/pr/1") + "\n"
            with self.subTest(kind=kind, field=field):
                with self.assertRaises(module.RecordError):
                    module.validate_record(kind, invalid)
                with self.assertRaises(module.jsonschema.ValidationError):
                    module.jsonschema.Draft202012Validator(module.schema_bundle()).validate(invalid)
        for char in map(chr, list(range(32)) + [127]):
            invalid = copy.deepcopy(records["run"])
            invalid["rig_root"] += char
            with self.subTest(char=repr(char)):
                with self.assertRaises(module.RecordError):
                    module.validate_record("run", invalid)


class WorkspaceSurfaceTests(unittest.TestCase):
    def test_review_and_fix_generation_owners_are_migration_surfaces(self):
        manifest = json.loads((CONTRACT_ROOT / "affected-surfaces.v1.json").read_text())
        required = [("gascity", "build-base", "review", {"review", "source-writer"}),
                    ("gascity", "build-basic", "review", {"review-delegator"}),
                    ("gascity", "fix-loop-base", "re-review", {"review-delegator"}),
                    ("gascity", "fix-convoy", "create-fix-convoy", {"fix-generation"})]
        required += [(pack, formula, "review", {"review-delegator"}) for pack, formula in
                     (("compound-engineering", "compound-build"), ("superpowers", "superpowers-build"),
                      ("bmad", "bmad-build"), ("gstack", "gstack-build"))]
        for pack, formula, step_id, roles in required:
            path = f"{pack}/formulas/{formula}.formula.toml"
            with self.subTest(formula=formula, step_id=step_id):
                matches = [b for b in manifest["owning_steps"] if b["formula"] == path and b["step_id"] == step_id]
                self.assertEqual(len(matches), 1, "missing concrete lifecycle owner")
                self.assertLessEqual(roles, set(matches[0]["roles"]))
                self.assertEqual(manifest["inventory"][matches[0]["asset"]]["classification"], "legacy")
                self.assertEqual(manifest["inventory"][path]["classification"], "legacy")

    def test_closed_manifest_covers_every_supported_formula_and_workflow_asset(self):
        manifest = json.loads((CONTRACT_ROOT / "affected-surfaces.v1.json").read_text())
        self.assertEqual(set(manifest["packs"]), SUPPORTED_PACKS)
        discovered = {str(path.relative_to(REPO_ROOT)) for pack in SUPPORTED_PACKS for root, pattern in (("formulas", "*.formula.toml"), ("assets/workflows", "*.md")) for path in (REPO_ROOT / pack / root).rglob(pattern)}
        self.assertEqual(discovered, set(manifest["inventory"]), "unclassified or missing formula/workflow asset")
        for path, row in manifest["inventory"].items():
            with self.subTest(path=path):
                self.assertIn(row["classification"], {"legacy", "new", "reference"})
                self.assertTrue(row["responsibility"])
                self.assertEqual(row["sha256"], hashlib.sha256((REPO_ROOT / path).read_bytes()).hexdigest())
        for owner in manifest["source_owners"]:
            with self.subTest(owner=owner["formula"]):
                self.assertTrue(owner["delegators"])
                self.assertIn(owner["final_source_step"]["asset"], manifest["inventory"])
                self.assertTrue(owner["final_source_step"]["step_id"])
                self.assertIn(owner["commit_contract"], {"explicit", "missing-explicit-commit"})
        self.assertEqual({(row["formula"].split("/")[0], row["context"]) for row in manifest["source_owners"]},
                         {(pack, context) for pack in SUPPORTED_PACKS for context in ("separate", "shared")})
        self.assertEqual(len(manifest["source_owners"]), 10)
        for path, row in manifest["source_helpers"].items():
            self.assertEqual(row["sha256"], hashlib.sha256((REPO_ROOT / path).read_bytes()).hexdigest())

    def test_manifest_step_and_delegation_bindings_match_current_formulas(self):
        manifest = json.loads((CONTRACT_ROOT / "affected-surfaces.v1.json").read_text())
        def declared_steps(path):
            data = tomllib.loads((REPO_ROOT / path).read_text())
            def walk(steps):
                for step in steps:
                    yield step
                    yield from walk(step.get("children", []))
            return {step["id"]: step for step in walk(data.get("steps", []) + data.get("template", []))}
        for binding in manifest["owning_steps"]:
            with self.subTest(binding=binding):
                step = declared_steps(binding["formula"])[binding["step_id"]]
                asset = (REPO_ROOT / binding["formula"]).parent / step["description_file"]
                self.assertEqual(str(asset.resolve().relative_to(REPO_ROOT)), binding["asset"])
        for owner in manifest["source_owners"]:
            self.assertEqual(owner["final_source_step"], next(binding for binding in manifest["owning_steps"]
                             if binding["formula"] == owner["formula"] and binding["step_id"] == owner["final_source_step"]["step_id"]))
            for delegator in owner["delegators"]:
                with self.subTest(delegator=delegator):
                    step = declared_steps(delegator["formula"])[delegator["step_id"]]
                    self.assertEqual(step["drain"]["formula"], pathlib.Path(owner["formula"]).name.removesuffix(".formula.toml"))
                    self.assertEqual(step["drain"]["context"], owner["context"])

    def test_all_rfc_scenarios_have_an_owner_and_observable_oracle(self):
        coverage = json.loads((CONTRACT_ROOT / "scenario-coverage.v1.json").read_text())
        self.assertEqual([row["scenario"] for row in coverage["scenarios"]], list(range(1, 24)))
        for row in coverage["scenarios"]:
            with self.subTest(scenario=row["scenario"]):
                self.assertTrue(row["implementation_owner"])
                self.assertTrue(row["oracle"])
                self.assertIn(row["status"], {"contract-tested", "implementation-required"})
        self.assertTrue(coverage["rfc_differences"])
        self.assertTrue(all("reason" in row and "contract" in row for row in coverage["rfc_differences"]))


if __name__ == "__main__":
    unittest.main()
