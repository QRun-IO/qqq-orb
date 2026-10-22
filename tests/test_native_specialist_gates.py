"""Native recognition proves central ownership and app-bound verification gates."""
import base64
import copy
from pathlib import Path
import sys
import unittest
from unittest import mock
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import native_specialist_gates as native
import reconcile_enrollment as remote
import enforce_orb_checks as enforcement
import finish_enrollment as finish


class NativeTests(unittest.TestCase):
    def fixture(self, repo):
        self.repo, self.pin, self.head = repo, 'a' * 40, 'b' * 40
        self.profile, self.branches, kinds, _ = native.DEFINITIONS[repo]
        self.callers = dict(native.caller(kind, self.pin) for kind in kinds)
        self.paths = list(self.callers)
        self.signed, self.drift, self.truncated = True, False, False
        self.mode = '100644'
        self.runs = [{'id': i, 'name': gate['context'], 'app': {'id': gate['app_id']},
                      'status': 'completed', 'conclusion': 'success'}
                     for i, gate in enumerate(native.gates(self.profile))]
        self.before = {'required_status_checks': {'strict': True, 'checks': native.gates(self.profile)},
                       'enforce_admins': {'enabled': True}}

    def request(self, path, method='GET', payload=None):
        self.assertEqual('GET', method)
        if '/contents/' in path:
            self.assertNotIn('.circleci/', path)
            file = path.split('/contents/')[1].split('?')[0]
            if path.startswith('repos/QRun-IO/qqq-orb/'):
                raw = (ROOT / file).read_text() + ('# changed' if self.drift else '')
            else:
                raw = yaml.safe_dump(self.callers[file], sort_keys=False)
            return {'type': 'file', 'encoding': 'base64', 'content': base64.b64encode(raw.encode()).decode()}
        if '/git/trees/' in path:
            return {'truncated': self.truncated, 'tree': [{'path': p, 'type': 'blob', 'mode': self.mode} for p in self.paths]}
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

    def test_all_approved_callers_discover_enforce_and_qualify_without_mutation(self):
        for repo in native.DEFINITIONS:
            self.fixture(repo)
            for branch in self.branches:
                with self.subTest(repo=repo, branch=branch), mock.patch.object(remote, 'api', side_effect=self.request):
                    plan = remote.inspect({'repository': repo, 'branch': branch}, '0.8')
                    self.assertEqual(self.profile, plan['profile'])
                    self.assertFalse(plan['changed'])
                    self.assertEqual(set(self.callers), set(plan['worker_pins']))
                    self.assertEqual({'state': 'unchanged'}, remote.apply(plan))
                    self.assertEqual({'state': 'unchanged'}, finish.merge_ready(plan, {'state': 'unchanged'}))
                    self.assertEqual([], finish.qualification(repo, self.head, self.profile))
                    protected = enforcement.inspect(repo, branch, '0.8', self.request)
                    self.assertFalse(protected['changed'])
                    enforcement.enforce(protected, self.request)

    def test_failed_missing_wrong_app_and_newer_failed_gate_reject(self):
        for repo in native.DEFINITIONS:
            self.fixture(repo)
            good = copy.deepcopy(self.runs)
            for bad in [[], good[1:], [dict(x, app={'id': 18001}) for x in good],
                        good + [dict(good[0], id=99, conclusion='failure')]]:
                self.runs = bad
                with self.subTest(repo=repo), self.assertRaises(ValueError):
                    enforcement.inspect(repo, 'main', '0.8', self.request)

    def test_custom_caller_unsigned_or_changed_worker_rejects(self):
        for repo in native.DEFINITIONS:
            for defect in ('caller', 'unsigned', 'worker', 'mutable'):
                self.fixture(repo)
                if defect == 'caller':
                    next(iter(self.callers.values()))['extra'] = True
                elif defect == 'unsigned':
                    self.signed = False
                elif defect == 'worker':
                    self.drift = True
                else:
                    jobs = next(iter(self.callers.values()))['jobs']
                    job = next(iter(jobs.values()))
                    job['uses'] = job['uses'].replace(self.pin, 'main')
                with self.subTest(repo=repo, defect=defect), self.assertRaises(ValueError):
                    native.validate(repo, self.head, 'main', self.request)

    def test_complete_workflow_inventory_required(self):
        self.fixture('QRun-IO/qqq-business-platform')
        for path in ('.circleci/config.yml', '.github/workflows/custom.yml', '.github/workflows/extra.yaml'):
            self.paths.append(path)
            with self.assertRaisesRegex(ValueError, 'additional orchestration'):
                native.validate(self.repo, self.head, 'main', self.request)
            self.paths.pop()
        self.truncated = True
        with self.assertRaisesRegex(ValueError, 'complete source tree'):
            native.validate(self.repo, self.head, 'main', self.request)

    def test_symlinked_or_missing_caller_rejects(self):
        self.fixture('QRun-IO/qctl')
        self.mode = '120000'
        with self.assertRaisesRegex(ValueError, 'regular source file'):
            native.validate(self.repo, self.head, 'main', self.request)
        self.paths = []
        with self.assertRaisesRegex(ValueError, 'regular source file'):
            native.validate(self.repo, self.head, 'main', self.request)

    def test_unknown_repo_and_unapproved_branch_reject(self):
        self.fixture('QRun-IO/qqq-mcp-rag')
        for repo, branch in [('QRun-IO/unknown', 'main'), (self.repo, 'develop'), ('QRun-IO/qctl', 'release/old')]:
            with self.assertRaises(ValueError):
                native.validate(repo, self.head, branch, self.request)

    def test_github_yaml_events_and_duplicate_keys(self):
        self.assertEqual({'on': {'push': None}, 'enabled': True},
                         native.load_workflow('on:\n  push:\nenabled: true\n'))
        for raw in ('on: {}\non: {}\n', 'jobs: {build: {}, build: {}}\n', '1: value\n'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                native.load_workflow(raw)

    def test_native_enforcement_preserves_other_required_checks(self):
        self.fixture('QRun-IO/qctl')
        self.before['required_status_checks']['checks'].append({'context': 'security', 'app_id': 15368})
        plan = enforcement.inspect(self.repo, 'main', '0.8', self.request)
        self.assertIn({'context': 'security', 'app_id': 15368}, plan['required_status_checks']['checks'])


if __name__ == '__main__':
    unittest.main()
