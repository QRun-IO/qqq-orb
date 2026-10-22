"""Remote enrollment keeps immutable source checks and resumes signed submissions."""
import base64
from pathlib import Path
import sys
import unittest
from unittest import mock

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import reconcile_enrollment as remote


class ReconcileTests(unittest.TestCase):
    def setUp(self):
        self.head = 'a' * 40
        self.new = 'b' * 40
        self.repo = 'QRun-IO/example'
        self.target = {'repository': self.repo, 'branch': 'main'}
        self.manifest = {'profile': 'qbit', 'orb_version': '0.7.4', 'default_branch': 'main',
                         'publish': {'snapshot': False, 'release_candidate': False, 'release': False}}
        self.sources = {
            '.qqq-ci.yml': yaml.safe_dump(self.manifest).encode(),
            '.circleci/config.yml': yaml.safe_dump(remote.enroll_consumers.rollout.standard.canonical_caller('qbit', '0.7.4')).encode()}

    def request(self, path, missing=False):
        if path == 'repos/' + self.repo:
            return {'archived': False, 'default_branch': 'main'}
        if path.endswith('/branches/main'):
            return {'commit': {'sha': self.head}}
        if '/contents/' in path:
            self.assertTrue(path.endswith('?ref=' + self.head))
            name = path.split('/contents/')[1].split('?')[0]
            raw = self.sources.get(name)
            return None if raw is None else {'type': 'file', 'encoding': 'base64', 'content': base64.b64encode(raw).decode()}
        raise AssertionError(path)

    def plan(self):
        with mock.patch.object(remote, 'api', side_effect=self.request):
            return remote.inspect(self.target, '0.8')

    def test_immutable_plan_is_deterministic_and_preserves_policy(self):
        first, second = self.plan(), self.plan()
        self.assertEqual(first['automation_branch'], second['automation_branch'])
        self.assertEqual(self.sources, first['originals'])
        self.assertEqual({**self.manifest, 'orb_version': '0.8'},
                         yaml.safe_load(first['replacements']['.qqq-ci.yml']))
        self.assertTrue(first['changed'])

    def test_missing_manifest_uses_legacy_converter(self):
        self.sources.pop('.qqq-ci.yml')
        self.sources['.circleci/config.yml'] = yaml.safe_dump({'version': 2.1,
            'orbs': {'qqq-orb': 'kingsrook/qqq-orb@0.5.0'},
            'workflows': {'verify': {'jobs': [{'qqq-orb/mvn_test_only': {}}]}}}).encode()
        plan = self.plan()
        self.assertIsNone(plan['originals']['.qqq-ci.yml'])
        self.assertFalse(any(yaml.safe_load(plan['replacements']['.qqq-ci.yml'])['publish'].values()))

    def submission_api(self, plan, path, missing=False):
        if '/branches/main' in path:
            return {'commit': {'sha': self.head}}
        if '/git/ref/' in path:
            return {'object': {'sha': self.new}}
        if '/commits/' in path:
            return {'commit': {'verification': {'verified': True}},
                    'parents': [{'sha': self.head}], 'files': [{'filename': p} for p in remote.PATHS]}
        if '/contents/' in path:
            self.assertTrue(path.endswith('?ref=' + self.new))
            name = path.split('/contents/')[1].split('?')[0]
            return {'type': 'file', 'encoding': 'base64', 'content': base64.b64encode(plan['replacements'][name]).decode()}
        if '/pulls?' in path:
            return [{'head': {'sha': self.new}, 'html_url': 'https://github.com/QRun-IO/example/pull/1'}]
        raise AssertionError(path)

    def test_matching_existing_submission_uses_no_git_or_pr_mutations(self):
        plan = self.plan()
        with mock.patch.object(remote, 'api', side_effect=lambda *a, **k: self.submission_api(plan, *a, **k)), mock.patch.object(remote, 'command') as command:
            result = remote.apply(plan)
        self.assertEqual('existing-pr', result['state'])
        command.assert_not_called()

    def test_unsigned_existing_branch_is_rejected_without_mutation(self):
        plan = self.plan()

        def request(path, missing=False):
            value = self.submission_api(plan, path, missing)
            if '/commits/' in path:
                value['commit']['verification']['verified'] = False
            return value

        with mock.patch.object(remote, 'api', side_effect=request), mock.patch.object(remote, 'command') as command:
            with self.assertRaises(ValueError):
                remote.apply(plan)
        command.assert_not_called()

    def test_source_drift_prevents_submission(self):
        plan = self.plan()
        with mock.patch.object(remote, 'api', return_value={'commit': {'sha': 'c' * 40}}), mock.patch.object(remote, 'command') as command:
            with self.assertRaises(ValueError):
                remote.apply(plan)
        command.assert_not_called()

    def test_interrupted_push_creates_only_missing_pr(self):
        plan = self.plan()
        seen = []

        def request(path, missing=False):
            return [] if '/pulls?' in path else self.submission_api(plan, path, missing)

        def command(args, cwd=None):
            seen.append(args[:3])
            self.assertEqual(['gh', 'pr', 'create'], args[:3])
            self.assertIn(self.head, Path(args[args.index('--body-file') + 1]).read_text())
            return 'https://github.com/QRun-IO/example/pull/2'

        with mock.patch.object(remote, 'api', side_effect=request), mock.patch.object(remote, 'command', side_effect=command):
            result = remote.apply(plan)
        self.assertEqual('submitted', result['state'])
        self.assertEqual([['gh', 'pr', 'create']], seen)

    def test_new_api_submission_is_atomic_and_exact(self):
        plan = self.plan()
        mutations = []

        def request(path, missing=False):
            if '/git/ref/' in path:
                return None
            return self.submission_api(plan, path, missing)

        def mutate(path, payload):
            mutations.append((path, payload))
            return {'data': {'createCommitOnBranch': {'commit': {'oid': self.new}}}}

        with mock.patch.object(remote, 'api', side_effect=request), mock.patch.object(remote, 'mutation', side_effect=mutate), mock.patch.object(remote, 'command') as command:
            self.assertEqual('existing-pr', remote.apply(plan)['state'])
        command.assert_not_called()
        self.assertEqual(('repos/' + self.repo + '/git/refs', {'ref': 'refs/heads/' + plan['automation_branch'], 'sha': self.head}), mutations[0])
        commit = mutations[1][1]['variables']['input']
        self.assertEqual(self.head, commit['expectedHeadOid'])
        self.assertEqual({'repositoryNameWithOwner': self.repo, 'branchName': plan['automation_branch']}, commit['branch'])
        self.assertEqual(plan['replacements'], {item['path']: base64.b64decode(item['contents']) for item in commit['fileChanges']['additions']})

    def test_base_only_branch_resumes_without_creating_another_ref(self):
        plan = self.plan()
        result = {'data': {'createCommitOnBranch': {'commit': {'oid': self.new}}}}
        with mock.patch.object(remote, 'api', return_value={'commit': {'sha': self.head}}), mock.patch.object(remote, 'mutation', return_value=result) as mutation:
            self.assertEqual(self.new, remote.signed_api_commit(plan, {'object': {'sha': self.head}}))
        self.assertEqual(1, mutation.call_count)
        self.assertEqual('graphql', mutation.call_args.args[0])

    def test_existing_completed_branch_is_not_mutated(self):
        with mock.patch.object(remote, 'mutation') as mutation:
            self.assertEqual(self.new, remote.signed_api_commit(self.plan(), {'object': {'sha': self.new}}))
        mutation.assert_not_called()

    def test_target_drift_prevents_commit_on_base_only_branch(self):
        plan = self.plan()
        with mock.patch.object(remote, 'api', return_value={'commit': {'sha': 'c' * 40}}), mock.patch.object(remote, 'mutation') as mutation:
            with self.assertRaises(ValueError):
                remote.signed_api_commit(plan, {'object': {'sha': self.head}})
        mutation.assert_not_called()

    def test_graphql_errors_fail_closed(self):
        response = mock.Mock(returncode=0, stdout='{"errors": [{"message": "conflict"}]}')
        with mock.patch.object(remote.subprocess, 'run', return_value=response):
            with self.assertRaises(ValueError):
                remote.mutation('graphql', {})

    def test_unsigned_api_commit_cannot_create_pr(self):
        plan = self.plan()
        def request(path, missing=False):
            if '/git/ref/' in path:
                return {'object': {'sha': self.head}}
            value = self.submission_api(plan, path, missing)
            if '/commits/' in path:
                value['commit']['verification']['verified'] = False
            return value
        with mock.patch.object(remote, 'api', side_effect=request), mock.patch.object(remote, 'mutation', return_value={'data': {'createCommitOnBranch': {'commit': {'oid': self.new}}}}), mock.patch.object(remote, 'command') as command:
            with self.assertRaises(ValueError):
                remote.apply(plan)
        command.assert_not_called()


if __name__ == '__main__':
    unittest.main()
