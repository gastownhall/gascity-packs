import unittest
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from full_e2e_interaction_cases import events, require_interrupted
from live_assertions import AcceptanceFailure


class InterruptionEvidenceTests(unittest.TestCase):
    def rows(self, status='interrupted'):
        return [
            {'type': 'client/turn/requested', 'data': {'requestId': 'request1'}},
            {'type': 'turn/input/accepted', 'data': {'clientRequestId': 'request1'}},
            {'type': 'turn/completed', 'data': {'status': status}},
        ]

    def test_stop_is_not_success_or_an_unrelated_acceptance(self):
        self.assertIsNotNone(require_interrupted(self.rows()))
        self.assertIsNone(require_interrupted([]))
        for status in ('failed', 'completed'):
            with self.assertRaises(AcceptanceFailure): require_interrupted(self.rows(status))
        rows = self.rows()
        rows[1]['data']['clientRequestId'] = 'another-request'
        with self.assertRaises(AcceptanceFailure): require_interrupted(rows)
        rows = self.rows()
        rows.append(rows[-1])
        with self.assertRaises(AcceptanceFailure): require_interrupted(rows)


class EventPaginationTests(unittest.TestCase):
    def setUp(self):
        self.runner = SimpleNamespace(manifest={'bbUrl': 'http://127.0.0.1:54321'})

    def test_more_than_two_pages_preserve_sparse_events_and_advance_by_real_sequence(self):
        expected = [{'seq': 15 + index * 2, 'data': {'value': index}} for index in range(237)]
        cursors = []
        def read(url):
            query = parse_qs(urlsplit(url).query)
            limit, after = int(query['limit'][0]), int(query['afterSeq'][0])
            self.assertLessEqual(limit, 100, 'BB rejects event limits above 100')
            self.assertEqual(query['order'], ['asc'])
            cursors.append(after)
            return [row for row in expected if row['seq'] > after][:limit]
        with patch('full_e2e_interaction_cases.read_json', side_effect=read):
            self.assertEqual(events(self.runner, 'thread', after=13), expected)
        self.assertEqual(cursors, [13, 213, 413])

    def test_exact_full_page_fetches_again_and_a_repeated_page_cannot_silently_truncate(self):
        expected = [{'seq': index + 1} for index in range(100)]
        with patch('full_e2e_interaction_cases.read_json', side_effect=[expected, []]) as read:
            self.assertEqual(events(self.runner, 'thread'), expected)
            self.assertEqual(read.call_count, 2)
        with patch('full_e2e_interaction_cases.read_json', return_value=expected):
            with self.assertRaisesRegex(AcceptanceFailure, 'did not advance'):
                events(self.runner, 'thread', after=100)


if __name__ == '__main__': unittest.main()
