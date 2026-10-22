"""Cost settings preserve source qualification and unrelated project controls."""
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import circle_project_settings as settings


class SettingsTests(unittest.TestCase):
    def setUp(self):
        self.plan = {'repository': 'QRun-IO/marketing-website', 'profile': 'marketing',
                     'branch': 'main', 'head': 'a' * 40, 'changed': False}
        self.before = {'autocancel-builds': False, 'setup-workflows': True,
                       'build-fork-prs': False, 'drop-all-build-requests': False}
        self.source = Mock(side_effect=[{'archived': False, 'default_branch': 'main'},
                                        {'commit': {'sha': self.plan['head']}}])

    def test_narrow_update_and_idempotent_readback(self):
        request = Mock(side_effect=[{'feature_flags': self.before}, {},
                                   {'feature_flags': {**self.before, 'autocancel-builds': True}}])
        result = settings.reconcile(self.plan, self.source, True, request)
        self.assertEqual({'state': 'enforced', 'changed': True}, result)
        self.assertEqual({'feature_flags': {'autocancel-builds': True}}, request.call_args_list[1].args[1])
        request = Mock(return_value={'feature_flags': {**self.before, 'autocancel-builds': True}})
        source = Mock(return_value={'archived': False, 'default_branch': 'main'})
        self.assertEqual({'state': 'enforced', 'changed': False},
                         settings.reconcile(self.plan, source, True, request))
        self.assertEqual(1, request.call_count)

    def test_dry_run_never_writes(self):
        request = Mock(return_value={'feature_flags': self.before})
        self.assertEqual({'state': 'inspected', 'changed': True},
                         settings.reconcile(self.plan, self.source, False, request))
        request.assert_called_once_with(self.plan['repository'])

    def test_unreviewed_profiles_and_unconverted_sources_never_call_api(self):
        for change, expected in [({'profile': 'qbit'}, 'not-managed'),
                                 ({'profile': 'native-gitops'}, 'not-managed'),
                                 ({'changed': True}, 'waiting-source')]:
            source, request = Mock(), Mock()
            result = settings.reconcile({**self.plan, **change}, source, True, request)
            self.assertEqual(expected, result['state'])
            source.assert_not_called()
            request.assert_not_called()

    def test_changed_head_or_unexpected_default_branch_prevents_write(self):
        for responses in [
            [{'archived': False, 'default_branch': 'main'}, {'commit': {'sha': 'b' * 40}}],
            [{'archived': False, 'default_branch': 'develop'}],
            [{'archived': True, 'default_branch': 'main'}],
        ]:
            request = Mock(return_value={'feature_flags': self.before})
            result = settings.reconcile(self.plan, Mock(side_effect=responses), True, request)
            self.assertEqual('unresolved', result['state'])
            self.assertTrue(all(len(call.args) == 1 for call in request.call_args_list))

    def test_unrelated_setting_drift_and_unavailable_api_are_not_success(self):
        request = Mock(side_effect=[{'feature_flags': self.before}, {},
                                   {'feature_flags': {**self.before, 'autocancel-builds': True,
                                                      'build-fork-prs': True}}])
        self.assertEqual('unresolved', settings.reconcile(self.plan, self.source, True, request)['state'])
        source = Mock(return_value={'archived': False, 'default_branch': 'main'})
        for response in [Mock(side_effect=ValueError('Central CircleCI credential unavailable')),
                         Mock(return_value={'feature_flags': {}})]:
            self.assertEqual('unresolved', settings.reconcile(self.plan, source, True, response)['state'])

    def test_repository_policy_requires_every_current_branch(self):
        main = {**self.plan, 'profile': 'repository-policy'}
        develop = {**main, 'branch': 'develop', 'profile': 'qbit'}
        for plans in ([main, develop], [develop, main]):
            source, request = Mock(), Mock()
            result = settings.reconcile_repository(plans, [], source, True, request)
            self.assertEqual('not-managed', result['state'])
            source.assert_not_called()
            request.assert_not_called()
        for plans, findings in [
            ([main, {**main, 'branch': 'develop', 'changed': True}], []),
            ([main], [{'repository': main['repository'], 'branch': 'develop', 'state': 'unresolved'}]),
        ]:
            request = Mock()
            self.assertEqual('waiting-source', settings.reconcile_repository(
                plans, findings, Mock(), True, request)['state'])
            request.assert_not_called()

    def test_repository_policy_checks_all_heads_and_writes_once(self):
        plans = [self.plan, {**self.plan, 'branch': 'develop', 'head': 'b' * 40}]
        def source(path):
            if '/branches/' in path:
                return {'commit': {'sha': next(p['head'] for p in plans if path.endswith('/' + p['branch']))}}
            return {'archived': False, 'default_branch': 'main'}
        request = Mock(side_effect=[{'feature_flags': self.before}, {},
                                   {'feature_flags': {**self.before, 'autocancel-builds': True}}])
        self.assertEqual({'state': 'enforced', 'changed': True},
                         settings.reconcile_repository(plans, [], source, True, request))
        self.assertEqual(1, sum(len(call.args) == 2 for call in request.call_args_list))
        request = Mock()
        stale = lambda path: {'commit': {'sha': self.plan['head']}}
        self.assertEqual('unresolved', settings.reconcile_repository(plans, [], stale, True, request)['state'])
        request.assert_not_called()


if __name__ == '__main__':
    unittest.main()
