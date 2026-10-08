import unittest
from e2e_matrix import required_cases

class MatrixTests(unittest.TestCase):
    def test_required_behavior_cannot_disappear_with_implementation(self):
        cases = required_cases(['none', 'medium'], desktop=True)
        for case in ('approvals.interrupt','lifecycle.busy_followup','lifecycle.interrupt',
                     'fault.bridge_uncertain_delivery','error.provider','error.startup','error.timeout',
                     'native.configured_agent','installation.fresh','desktop.native'):
            self.assertIn(case,cases)
        self.assertEqual(len(cases),len(set(cases)))

    def test_every_advertised_level_remains_required(self):
        self.assertIn('reasoning.max',required_cases(['none','low','medium','high','max']))
        with self.assertRaises(ValueError): required_cases(['medium'])
