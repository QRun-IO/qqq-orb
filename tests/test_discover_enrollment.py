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
