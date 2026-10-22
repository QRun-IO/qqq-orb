"""Native GitOps discovery must prove shared ownership without adding Circle jobs."""
import base64
import copy
from pathlib import Path
import sys
import unittest
from unittest import mock
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import native_gitops_gates as gitops
import reconcile_enrollment as remote
import enforce_orb_checks as enforcement
import finish_enrollment as finish

class GitOpsTests(unittest.TestCase):
    def setUp(self):
        self.pin, self.head = 'a' * 40, 'b' * 40
        self.repo = 'QRun-IO/voyage-cd'
        self.caller = gitops.bridge.canonical('gitops', self.pin)
        self.signed, self.worker_drift, self.truncated = True, False, False
        self.paths = ['.github/workflows/validate.yml', 'base/kustomization.yaml']
        self.runs = [{'id': 1, 'name': 'gitops / validate', 'app': {'id': 15368},
                      'status': 'completed', 'conclusion': 'success'}]
        self.before = {'required_status_checks': {'strict': True, 'checks': gitops.gates()},
                       'enforce_admins': {'enabled': True}}

    def request(self, path, method='GET', payload=None):
        self.assertEqual(method, 'GET')
        if '/contents/' in path:
            self.assertNotIn('.circleci/', path)
            if '/QRun-IO/qqq-orb/' in path:
                raw = (ROOT / '.github/workflows/gitops.yml').read_text() + ('# drift' if self.worker_drift else '')
            else:
                raw = yaml.safe_dump(self.caller, sort_keys=False)
            return {'type': 'file', 'encoding': 'base64', 'content': base64.b64encode(raw.encode()).decode()}
        if '/git/trees/' in path:
            return {'truncated': self.truncated, 'tree': [{'path': p} for p in self.paths]}
        if path.endswith('/commits/' + self.pin):
            return {'commit': {'verification': {'verified': self.signed}}}
        if '/check-runs?' in path:
            return {'check_runs': copy.deepcopy(self.runs)}
        if '/status?' in path:
            return {'statuses': []}
        if path.endswith('/protection'):
            return copy.deepcopy(self.before)
        if '/rules/branches/' in path:
            return []
        if '/branches/' in path:
            return {'commit': {'sha': self.head}}
        return {'archived': False, 'default_branch': 'main'}

    def test_discovery_returns_unchanged_native_plan_without_circle_reads_or_writes(self):
        for repo in sorted(gitops.REPOSITORIES):
            with mock.patch.object(remote, 'api', side_effect=self.request):
                plan = remote.inspect({'repository': repo, 'branch': 'main'}, '0.8')
            self.assertEqual(plan['profile'], 'native-gitops')
            self.assertFalse(plan['changed'])
            self.assertEqual(plan['worker_pin'], self.pin)
            self.assertEqual(remote.apply(plan), {'state': 'unchanged'})
            self.assertEqual(finish.merge_ready(plan, {'state': 'unchanged'}), {'state': 'unchanged'})

    def test_enforcement_retains_bound_native_gate(self):
        plan = enforcement.inspect(self.repo, 'main', '0.8', self.request)
        self.assertFalse(plan['changed'])
        self.assertEqual(plan['gates'], gitops.gates())
        enforcement.enforce(plan, self.request)

    def test_wrong_app_and_failed_gate_reject(self):
        for field, value in [('app', {'id': 18001}), ('conclusion', 'failure')]:
            original = copy.deepcopy(self.runs)
            self.runs[0][field] = value
            with self.assertRaises(ValueError):
                enforcement.inspect(self.repo, 'main', '0.8', self.request)
            self.runs = original

    def test_noncanonical_or_unsigned_or_changed_worker_rejects(self):
        self.caller['jobs']['gitops']['uses'] = 'other/repo/workflow.yml@' + self.pin
        with self.assertRaisesRegex(ValueError, 'canonical'):
            gitops.validate(self.repo, self.head, 'main', self.request, yaml.safe_load)
        self.caller = gitops.bridge.canonical('gitops', self.pin)
        self.signed = False
        with self.assertRaisesRegex(ValueError, 'not verified'):
            gitops.validate(self.repo, self.head, 'main', self.request, yaml.safe_load)
        self.signed, self.worker_drift = True, True
        with self.assertRaisesRegex(ValueError, 'supported contract'):
            gitops.validate(self.repo, self.head, 'main', self.request, yaml.safe_load)

    def test_additional_orchestration_and_incomplete_inventory_reject(self):
        for path in ['.circleci/config.yml', '.github/workflows/custom.yaml']:
            self.paths.append(path)
            with self.assertRaisesRegex(ValueError, 'additional orchestration'):
                gitops.validate(self.repo, self.head, 'main', self.request, yaml.safe_load)
            self.paths.pop()
        self.truncated = True
        with self.assertRaisesRegex(ValueError, 'complete source tree'):
            gitops.validate(self.repo, self.head, 'main', self.request, yaml.safe_load)

    def test_unknown_repository_and_develop_are_not_exempted(self):
        for repo, branch in [('QRun-IO/unknown', 'main'), (self.repo, 'develop')]:
            with self.assertRaises(ValueError):
                gitops.validate(repo, self.head, branch, self.request, yaml.safe_load)

    def test_native_pr_qualification(self):
        with mock.patch.object(finish.remote, 'api', side_effect=self.request):
            self.assertEqual(finish.qualification(self.repo, self.head, 'native-gitops'), [])
            self.runs = []
            self.assertEqual(finish.qualification(self.repo, self.head, 'native-gitops'), ['gitops / validate'])

if __name__ == '__main__':
    unittest.main()
