"""Prepared manifests select the exact test roles, never similarly named agents."""
import copy
import unittest

from live_acceptance import GateError, acceptance_agents


class AcceptanceAgentTests(unittest.TestCase):
    def setUp(self):
        self.global_agent = {"agent": "global", "rig": "", "connection": "local", "city": "scratch",
            "id": "gc1_global", "provider": "claude", "reasoningLevels": ["none", "medium"]}
        self.rig_agent = {**self.global_agent, "agent": "sample/rig", "rig": "sample", "id": "gc1_rig"}

    def test_default_and_unrelated_agents_cannot_pollute_prepared_manifest(self):
        rows = [{"agent": "mayor", "rig": ""}, self.rig_agent,
                {"agent": "sample/worker", "rig": "sample"}, self.global_agent]
        before = copy.deepcopy(rows)
        self.assertEqual(acceptance_agents(rows), [self.rig_agent, self.global_agent])
        self.assertEqual(rows, before)

    def test_scope_and_expanded_rig_identity_must_both_match(self):
        for replacement in ({**self.rig_agent, "agent": "rig"},
                            {**self.rig_agent, "rig": "another-rig"},
                            {**self.global_agent, "rig": "sample"}):
            with self.subTest(replacement=replacement), self.assertRaises(GateError):
                other = self.global_agent if replacement["agent"] != "global" else self.rig_agent
                acceptance_agents([other, replacement])

    def test_missing_or_duplicate_exact_roles_fail_instead_of_arbitrary_selection(self):
        for rows in ([], [self.global_agent], [self.rig_agent],
                     [self.global_agent, self.global_agent],
                     [self.global_agent, self.rig_agent, {**self.rig_agent, "connection": "another"}]):
            with self.subTest(rows=rows), self.assertRaises(GateError): acceptance_agents(rows)

    def test_global_without_optional_rig_field_keeps_its_metadata(self):
        global_agent = {key: value for key, value in self.global_agent.items() if key != "rig"}
        self.assertEqual(acceptance_agents([global_agent, self.rig_agent]), [global_agent, self.rig_agent])


if __name__ == "__main__": unittest.main()
