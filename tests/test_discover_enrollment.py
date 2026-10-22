"""Discovery covers all current branches and never turns an unknown into a target."""
from pathlib import Path
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import discover_enrollment as discovery


def entry(name, archived=False):
    return {'nameWithOwner': 'QRun-IO/' + name, 'isArchived': archived}


class DiscoveryTests(unittest.TestCase):
    def policy(self):
        return {'QRun-IO/example': {'baseline_sha': 'a' * 40, 'required_paths': ['README.md'],
                'forbidden_paths': ['.qqq-ci.yml'], 'forbidden_prefixes': ['.circleci/', '.github/workflows/'],
                'rationale': 'Approved documentation-only snapshot'}}

    def test_approved_snapshot_is_reported_without_enrollment(self):
        def request(path):
            if '/branches?' in path:
                return [{'name': 'main'}, {'name': 'develop'}]
            if '/branches/' in path:
                return {'commit': {'sha': ('a' if path.endswith('main') else 'b') * 40}}
            return {'truncated': False, 'tree': [{'path': 'README.md', 'type': 'blob'}]}
        inspect = mock.Mock(side_effect=lambda target, version: target)
        with mock.patch.dict(discovery.audit_estate.NO_CI, self.policy(), clear=True):
            plans, findings = discovery.discover('QRun-IO', '0.8', inspect, request, [entry('example')])
        self.assertEqual([{'repository': 'QRun-IO/example', 'branch': 'develop'}], plans)
        self.assertEqual('approved-no-ci', findings[0]['state'])
        self.assertEqual('a' * 40, findings[0]['head'])
        inspect.assert_called_once_with(plans[0], '0.8')

    def test_no_ci_tree_must_be_complete_and_match_approved_identity(self):
        for tree in ({'truncated': True, 'tree': [{'path': 'README.md'}]},
                     {'truncated': False, 'tree': []},
                     {'truncated': False, 'tree': [{'path': 'README.md'}, {'path': '.circleci/config.yml'}]}):
            def request(path):
                if '/branches?' in path:
                    return [{'name': 'main'}]
                if '/branches/' in path:
                    return {'commit': {'sha': 'a' * 40}}
                return tree
            inspect = mock.Mock()
            with mock.patch.dict(discovery.audit_estate.NO_CI, self.policy(), clear=True):
                plans, findings = discovery.discover('QRun-IO', '0.8', inspect, request, [entry('example')])
            self.assertEqual([], plans)
            self.assertEqual('unresolved', findings[0]['state'])
            inspect.assert_not_called()

    def test_old_no_ci_label_never_exempts_executable_or_deployment_source(self):
        for source in ('base/deployment.yaml', 'template/pom.xml', 'scripts/customize.py', 'Formula/qctl.rb'):
            def request(path):
                if '/branches?' in path:
                    return [{'name': 'main'}]
                if '/branches/' in path:
                    return {'commit': {'sha': 'a' * 40}}
                return {'truncated': False, 'tree': [{'path': 'README.md', 'type': 'blob'},
                                                   {'path': source, 'type': 'blob'}]}
            inspect = mock.Mock(side_effect=ValueError('Source needs centralized validation'))
            with mock.patch.dict(discovery.audit_estate.NO_CI, self.policy(), clear=True):
                plans, findings = discovery.discover('QRun-IO', '0.8', inspect, request, [entry('example')])
            self.assertEqual([], plans)
            self.assertEqual('unresolved', findings[0]['state'])
            inspect.assert_called_once()

    def test_changed_no_ci_source_is_never_exempted(self):
        def request(path):
            if '/branches?' in path:
                return [{'name': 'main'}]
            return {'commit': {'sha': 'b' * 40}}
        inspect = mock.Mock(side_effect=ValueError('Unrecognized executable source'))
        with mock.patch.dict(discovery.audit_estate.NO_CI, self.policy(), clear=True):
            plans, findings = discovery.discover('QRun-IO', '0.8', inspect, request, [entry('example')])
        self.assertEqual([], plans)
        self.assertEqual('unresolved', findings[0]['state'])
        inspect.assert_called_once()

    def test_paginates_branches_and_ignores_historical_releases(self):
        requests = []

        def request(path):
            requests.append(path)
            if path.endswith('page=1'):
                return [{'name': 'release/' + str(i)} for i in range(99)] + [{'name': 'main'}]
            return [{'name': 'develop'}]

        inspect = mock.Mock(side_effect=lambda target, version: {**target, 'version': version})
        plans, findings = discovery.discover('QRun-IO', '0.8', inspect, request, [entry('example')])
        self.assertEqual(['develop', 'main'], [p['branch'] for p in plans])
        self.assertEqual(2, len(requests))
        self.assertEqual([], findings)

    def test_unknown_branch_and_profile_stay_unresolved_while_other_targets_progress(self):
        def inspect(target, version):
            if target['repository'].endswith('/custom'):
                raise ValueError('Unknown orchestration')
            return target

        def request(path):
            return [{'name': 'feature/new'}] if '/new/' in path else [{'name': 'main'}]

        plans, findings = discovery.discover('QRun-IO', '0.8', inspect, request,
                                             [entry('custom'), entry('new'), entry('good')])
        self.assertEqual([{'repository': 'QRun-IO/good', 'branch': 'main'}], plans)
        self.assertEqual(2, len(findings))
        self.assertTrue(all(f['state'] == 'unresolved' for f in findings))

    def test_archived_and_owner_repositories_are_never_modified(self):
        inspect, request = mock.Mock(), mock.Mock()
        plans, findings = discovery.discover('QRun-IO', '0.8', inspect, request,
                                             [entry('old', True), entry('qqq-orb')])
        self.assertEqual([], plans)
        self.assertEqual(['archived', 'owner-bootstrap'], [f['state'] for f in findings])
        inspect.assert_not_called()
        request.assert_not_called()

    def test_api_errors_and_duplicate_branches_never_become_empty_success(self):
        for result in (ValueError('GitHub read unavailable'), [{'name': 'main'}, {'name': 'main'}]):
            request = mock.Mock(side_effect=result) if isinstance(result, Exception) else mock.Mock(return_value=result)
            inspect = mock.Mock()
            plans, findings = discovery.discover('QRun-IO', '0.8', inspect, request, [entry('example')])
            self.assertEqual([], plans)
            self.assertEqual('unresolved', findings[0]['state'])
            inspect.assert_not_called()


if __name__ == '__main__':
    unittest.main()
