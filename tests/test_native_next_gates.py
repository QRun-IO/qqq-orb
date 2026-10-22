"""Recognize native ownership without duplicate CI or weaker PR protections."""
import base64
import copy
from pathlib import Path
import sys
import unittest
from unittest import mock
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import enforce_orb_checks as enforcement
import finish_enrollment as finish


class NativeTests(unittest.TestCase):
    def setUp(self):
        self.pin = 'a' * 40
        self.head = 'b' * 40
        self.caller = enforcement.native.bridge.canonical_next(self.pin)
        self.signed = True
        self.worker_drift = False
        self.runs = [{'id': i, 'name': gate['context'], 'app': {'id': 15368},
                      'status': 'completed', 'conclusion': 'success'}
                     for i, gate in enumerate(enforcement.native.gates())]
        self.record = {'id': 1, 'enforcement': 'active', 'target': 'branch',
                       'source_type': 'Repository', 'source': 'QRun-IO/example', 'bypass_actors': [],
                       'rules': [{'type': 'required_status_checks', 'parameters': {
                           'strict_required_status_checks_policy': False,
                           'required_status_checks': [{'context': g['context'], 'integration_id': g['app_id']}
                                                      for g in enforcement.gates('frontend-next')]}}]}

    def request(self, path, method='GET', payload=None):
        self.assertEqual('GET', method, 'Recognition must not mutate correct protections')
        if '/contents/' in path:
            if '.github/workflows/ci.yml?' in path:
                raw = yaml.safe_dump(self.caller)
            elif 'repos/QRun-IO/qqq-orb/' in path:
                name = path.split('/contents/')[1].split('?')[0]
                raw = (ROOT / name).read_text(encoding='utf-8') + ('# drift' if self.worker_drift else '')
            else:
                data = ({'profile': 'frontend-next', 'orb_version': '0.8', 'default_branch': 'main'}
                        if '/.qqq-ci.yml?' in path else enforcement.standard.canonical_caller('frontend-next', '0.8'))
                raw = yaml.safe_dump(data)
            return {'type': 'file', 'encoding': 'base64', 'content': base64.b64encode(raw.encode()).decode()}
        if path.endswith('/commits/' + self.pin):
            return {'commit': {'verification': {'verified': self.signed}}}
        if '/check-runs?' in path:
            return {'check_runs': copy.deepcopy(self.runs)}
        if '/status?' in path:
            return {'statuses': []}
        if '/rulesets/1' in path:
            return copy.deepcopy(self.record)
        if '/rules/branches/' in path:
            return [{'type': 'required_status_checks', 'ruleset_source_type': 'Repository',
                     'ruleset_source': 'QRun-IO/example', 'ruleset_id': 1}]
        if path.endswith('/protection'):
            return None
        if '/branches/' in path:
            return {'commit': {'sha': self.head}}
        return {'archived': False}

    def test_main_recognition_retains_all_eight_pr_gates_without_image_run(self):
        plan = enforcement.inspect('QRun-IO/example', 'main', '0.8', self.request)
        self.assertFalse(plan['changed'])
        self.assertEqual('rulesets', plan['protection_mode'])
        self.assertEqual(enforcement.gates('frontend-next'), plan['required_status_checks']['checks'])
        self.assertEqual(8, len(plan['gates']))
        enforcement.enforce(plan, self.request)

    def test_caller_drift_unsigned_and_changed_workers_fail_closed(self):
        self.caller['jobs']['ci']['uses'] = 'untrusted/repo/ci.yml@' + self.pin
        with self.assertRaisesRegex(ValueError, 'canonical'):
            enforcement.inspect('QRun-IO/example', 'main', '0.8', self.request)
        self.caller = enforcement.native.bridge.canonical_next(self.pin)
        self.signed = False
        with self.assertRaisesRegex(ValueError, 'not verified'):
            enforcement.inspect('QRun-IO/example', 'main', '0.8', self.request)
        self.signed = True
        self.worker_drift = True
        with self.assertRaisesRegex(ValueError, 'supported contract'):
            enforcement.inspect('QRun-IO/example', 'main', '0.8', self.request)

    def test_missing_main_gate_wrong_app_and_missing_pr_protection_reject(self):
        self.runs[0]['app']['id'] = 18001
        with self.assertRaises(ValueError):
            enforcement.inspect('QRun-IO/example', 'main', '0.8', self.request)
        self.runs[0]['app']['id'] = 15368
        self.record['rules'][0]['parameters']['required_status_checks'].pop()
        with self.assertRaisesRegex(ValueError, 'missing app-bound gate'):
            enforcement.inspect('QRun-IO/example', 'main', '0.8', self.request)

    def test_pr_qualification_requires_both_image_architectures(self):
        with mock.patch.object(finish.remote, 'api', side_effect=self.request):
            missing = finish.qualification('QRun-IO/example', self.head, 'frontend-next')
            self.assertEqual(sorted(enforcement.native.PR_GATES[-2:]), missing)
            for i, name in enumerate(enforcement.native.PR_GATES[-2:], 20):
                self.runs.append({'id': i, 'name': name, 'app': {'id': 15368},
                                  'status': 'completed', 'conclusion': 'success'})
            self.assertEqual([], finish.qualification('QRun-IO/example', self.head, 'frontend-next'))

    def test_develop_has_no_native_push_contract(self):
        with self.assertRaisesRegex(ValueError, 'main only'):
            enforcement.native.validate('QRun-IO/example', self.head, 'develop', self.request, enforcement.standard.load_yaml)


if __name__ == '__main__':
    unittest.main()
