"""Shared enforcement only adds proven gates and preserves unrelated policy."""
import copy
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('enforcement', Path(__file__).resolve().parents[1] / 'tools/enforce_orb_checks.py')
enforcement = importlib.util.module_from_spec(spec)
spec.loader.exec_module(enforcement)


def runs():
    return [{'id': index, 'name': name, 'app': {'id': 18001}, 'conclusion': 'success'}
            for index, name in enumerate(('setup', 'verify'), 1)]


class EnforcementTests(unittest.TestCase):
    def test_preserves_security_gate_and_binds_orb_checks(self):
        before = {'required_status_checks': {'strict': False, 'contexts': ['security', 'setup'],
                  'checks': [{'context': 'security', 'app_id': 15368}, {'context': 'setup', 'app_id': -1}]}}
        original = copy.deepcopy(before)
        result = enforcement.required_checks(before, runs())
        self.assertEqual(original, before)
        self.assertEqual(result, {'strict': True, 'checks': [{'context': 'security', 'app_id': 15368}, *enforcement.DESIRED]})

    def test_wrong_app_failed_latest_and_missing_checks_reject(self):
        cases = [[], [runs()[0]], [dict(run, app={'id': 999}) for run in runs()],
                 runs() + [dict(runs()[1], id=3, conclusion='failure')]]
        for candidate in cases:
            with self.subTest(candidate=candidate), self.assertRaises(ValueError):
                enforcement.required_checks(None, candidate)
        with self.assertRaises(ValueError):
            enforcement.required_checks({'required_status_checks': {'checks': [{'context': 'verify', 'app_id': 999}]}}, runs())

    def test_existing_unrestricted_contexts_are_retained(self):
        result = enforcement.required_checks({'required_status_checks': {'contexts': ['legacy-build']}}, runs())
        self.assertIn({'context': 'legacy-build', 'app_id': -1}, result['checks'])

    def fixture(self, before):
        state = {'before': copy.deepcopy(before), 'head': 'a' * 40, 'writes': []}
        def request(path, method='GET', payload=None):
            if method != 'GET':
                state['writes'].append((method, path, payload))
                if method == 'PUT':
                    state['before'] = {**payload, 'enforce_admins': {'enabled': True}}
                elif method == 'PATCH':
                    state['before']['required_status_checks'] = copy.deepcopy(payload)
                elif method == 'POST':
                    state['before']['enforce_admins'] = {'enabled': True}
                return None
            if '/rules/' in path:
                return []
            if path.endswith('/protection'):
                return copy.deepcopy(state['before'])
            return {'commit': {'sha': state['head']}}
        plan = {'repository': 'QRun-IO/example', 'branch': 'develop', 'head': 'a' * 40,
                'before': copy.deepcopy(before), 'required_status_checks': enforcement.required_checks(before, runs()), 'changed': True}
        return plan, request, state

    def test_narrow_updates_preserve_reviews_signatures_and_restrictions(self):
        before = {'required_status_checks': {'strict': False, 'checks': []}, 'enforce_admins': {'enabled': False},
                  'required_signatures': {'enabled': True}, 'required_linear_history': {'enabled': True},
                  'required_pull_request_reviews': {'required_approving_review_count': 2},
                  'restrictions': {'users': [{'login': 'owner'}]}}
        plan, request, state = self.fixture(before)
        enforcement.enforce(plan, request)
        self.assertEqual(['PATCH', 'POST'], [write[0] for write in state['writes']])
        for key in ('required_signatures', 'required_linear_history', 'required_pull_request_reviews', 'restrictions'):
            self.assertEqual(before[key], state['before'][key])

    def test_new_protection_and_idempotent_noop(self):
        plan, request, state = self.fixture(None)
        enforcement.enforce(plan, request)
        self.assertEqual('PUT', state['writes'][0][0])
        self.assertIsNone(state['before']['required_pull_request_reviews'])
        plan['before'] = copy.deepcopy(state['before'])
        plan['changed'] = False
        state['writes'] = []
        enforcement.enforce(plan, request)
        self.assertEqual([], state['writes'])

    def test_head_or_protection_drift_never_mutates(self):
        for field, value in [('head', 'b' * 40), ('before', {'unexpected': True})]:
            plan, request, state = self.fixture(None)
            state[field] = value
            with self.assertRaises(ValueError):
                enforcement.enforce(plan, request)
            self.assertEqual([], state['writes'])


if __name__ == '__main__':
    unittest.main()
