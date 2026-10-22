"""Automatic completion requires qualified source and preserves normal merge policy."""
import json
from pathlib import Path
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import finish_enrollment as finish


class FinishTests(unittest.TestCase):
    def setUp(self):
        self.plan = {'repository': 'QRun-IO/example', 'branch': 'main', 'head': 'a' * 40,
                     'profile': 'qbit', 'version': '0.8'}
        self.result = {'state': 'existing-pr', 'head': 'b' * 40, 'url': 'https://github.com/QRun-IO/example/pull/1'}
        self.pr = {'number': 1, 'state': 'OPEN', 'headRefOid': 'b' * 40,
                   'baseRefOid': 'a' * 40, 'baseRefName': 'main', 'mergeCommit': None}

    def checks(self):
        return [{'id': i, 'name': name, 'app': {'id': 18001}, 'status': 'completed', 'conclusion': 'success'}
                for i, name in enumerate(('setup', 'verify'))]

    def test_all_checks_and_statuses_must_pass_and_gates_must_use_circle_app(self):
        checks = self.checks()
        checks[1]['app']['id'] = 123
        checks.append({'id': 3, 'name': 'scanner', 'app': {'id': 15368}, 'status': 'completed', 'conclusion': 'failure'})
        with mock.patch.object(finish.remote, 'api', side_effect=[{'check_runs': checks},
                {'statuses': [{'context': 'legacy-test', 'state': 'pending'}]}]):
            self.assertEqual(['legacy-test', 'scanner', 'verify'], finish.qualification('QRun-IO/example', 'b' * 40))

    def test_profile_qualification_requires_its_actual_workflow(self):
        for profile in ('all', 'cli', 'android', 'app-starter', 'mcp-policy'):
            checks = self.checks()
            checks[1]['name'] = finish.enforcement.PROFILE_GATES[profile]
            with mock.patch.object(finish.remote, 'api', side_effect=[
                    {'check_runs': checks}, {'statuses': []}]):
                self.assertEqual([], finish.qualification('QRun-IO/example', 'b' * 40, profile))
            with mock.patch.object(finish.remote, 'api', side_effect=[
                    {'check_runs': self.checks()}, {'statuses': []}]):
                self.assertEqual([checks[1]['name']], finish.qualification('QRun-IO/example', 'b' * 40, profile))

    def test_failed_or_missing_checks_never_merge(self):
        with mock.patch.object(finish.remote, 'verify_submission'), mock.patch.object(finish.remote, 'command', return_value=json.dumps(self.pr)) as command, mock.patch.object(finish.remote, 'api', return_value={'commit': {'sha': self.plan['head']}}), mock.patch.object(finish, 'qualification', return_value=['verify']):
            self.assertEqual('waiting-checks', finish.merge_ready(self.plan, self.result)['state'])
        self.assertEqual(1, command.call_count)
        self.assertEqual(['gh', 'pr', 'view'], command.call_args.args[0][:3])

    def test_stale_base_never_merges_even_when_checks_were_green(self):
        self.pr['baseRefOid'] = 'c' * 40
        with mock.patch.object(finish.remote, 'verify_submission'), mock.patch.object(finish.remote, 'command', return_value=json.dumps(self.pr)) as command:
            self.assertEqual('stale-base', finish.merge_ready(self.plan, self.result)['state'])
        self.assertEqual(1, command.call_count)

    def test_success_uses_exact_head_normal_merge_and_verifies_result(self):
        calls = []

        def command(args):
            calls.append(args)
            if args[2] == 'merge':
                return ''
            if len(calls) == 1:
                return json.dumps(self.pr)
            return json.dumps({'state': 'MERGED', 'mergeCommit': {'oid': 'd' * 40}})

        def api(path):
            if '/branches/' in path:
                return {'commit': {'sha': self.plan['head']}}
            return {'commit': {'tree': {'sha': 'e' * 40}, 'verification': {'verified': True}}}

        with mock.patch.object(finish.remote, 'verify_submission'), mock.patch.object(finish.remote, 'command', side_effect=command), mock.patch.object(finish.remote, 'api', side_effect=api), mock.patch.object(finish, 'qualification', return_value=[]):
            result = finish.merge_ready(self.plan, self.result)
        self.assertEqual('merged', result['state'])
        self.assertEqual(['gh', 'pr', 'merge', '1', '--repo', 'QRun-IO/example', '--squash', '--match-head-commit', 'b' * 40], calls[1])

    def test_enforcement_waits_for_current_head_and_uses_shared_preserving_writer(self):
        with mock.patch.object(finish.enforcement, 'inspect', side_effect=ValueError('Current branch has no successful verify')), mock.patch.object(finish.enforcement, 'enforce') as enforce:
            self.assertEqual('waiting-enforcement', finish.enforce_current(self.plan)['state'])
            enforce.assert_not_called()
        current = {'head': 'd' * 40, 'changed': True}
        with mock.patch.object(finish.enforcement, 'inspect', return_value=current), mock.patch.object(finish.enforcement, 'enforce') as enforce:
            self.assertEqual('enforced', finish.enforce_current(self.plan)['state'])
            enforce.assert_called_once_with(current)

    def test_unknown_gate_profile_never_merges_or_enforces(self):
        self.plan['profile'] = 'unknown-profile'
        with mock.patch.object(finish.remote, 'command') as command, mock.patch.object(finish.enforcement, 'inspect') as inspect:
            self.assertEqual('unsupported-gates', finish.merge_ready(self.plan, self.result)['state'])
            self.assertEqual('unsupported-gates', finish.enforce_current(self.plan)['state'])
            command.assert_not_called()
            inspect.assert_not_called()

    def test_merged_tree_mismatch_is_not_reported_as_success(self):
        self.pr.update(state='MERGED', mergeCommit={'oid': 'd' * 40})
        with mock.patch.object(finish.remote, 'verify_submission'), mock.patch.object(finish.remote, 'command', return_value=json.dumps(self.pr)), mock.patch.object(finish.remote, 'api', side_effect=[
                {'commit': {'tree': {'sha': 'e' * 40}}},
                {'commit': {'tree': {'sha': 'f' * 40}, 'verification': {'verified': True}}}]):
            with self.assertRaises(ValueError):
                finish.merge_ready(self.plan, self.result)


if __name__ == '__main__':
    unittest.main()
