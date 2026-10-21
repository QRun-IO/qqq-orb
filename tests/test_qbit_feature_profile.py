"""Preserve Workflows' audited publish-tag contract without broadening branches."""
import unittest
from unittest import mock
from pathlib import Path
import yaml
from test_qbit_hotfix_profile import load, migration, pipeline, selects, ROOT

standard = load('standard', 'src/scripts/validate_standard.py')


class FeaturePublicationTests(unittest.TestCase):
    def config(self, manifest):
        with mock.patch.object(Path, 'read_text', return_value=yaml.safe_dump(manifest)):
            return pipeline.load_manifest('unused', '0.7.16')

    def test_audited_event_selection_matches_legacy(self):
        legacy = yaml.safe_load((ROOT / 'tests/fixtures/qbit-feature-publication.yml').read_text())
        manifest = migration.infer_manifest(legacy, '0.7.16', 'main')
        self.assertTrue(manifest['publish']['feature'])
        caller = migration.canonical_caller('0.7.16', manifest['release_tag_policy'], True)
        standard.validate(yaml.safe_dump(caller), yaml.safe_dump(manifest), '0.7.16')
        setup = caller['workflows']['setup']['jobs'][0]['qqq-orb/generate_pipeline']
        cases = [(branch, '') for branch in ['main', 'develop', 'feature/example', 'release/0.3.0', 'hotfix/0.3.1', 'integration-test']]
        cases += [('', tag) for tag in ['publish', 'publish-example', 'v1.2.3', 'v1.2.3-RC.1', 'other']]
        for branch, tag in cases:
            with self.subTest(branch=branch, tag=tag):
                expected = sorted((job, args.get('branch_type')) for workflow in legacy['workflows'].values()
                                  for entry in workflow['jobs'] for job, args in entry.items()
                                  if selects(args.get('filters', {}), branch, tag))
                with mock.patch.object(pipeline, 'git', return_value=b'verified-head\n'):
                    rendered = pipeline.qbit_template(self.config(manifest), branch, tag)
                actual = sorted((job, args.get('branch_type')) for workflow in rendered['workflows'].values()
                                for entry in workflow['jobs'] for job, args in entry.items()
                                if selects(args.get('filters', {}), branch, tag))
                if not selects(setup['filters'], branch, tag):
                    actual = []
                self.assertEqual(expected, actual)

    def test_feature_is_opt_in_and_requires_exact_tag_head(self):
        manifest = {'profile': 'qbit', 'orb_version': '0.7.16', 'default_branch': 'main'}
        self.assertFalse(self.config(manifest)['publish']['feature'])
        manifest['publish'] = {'feature': True}
        for tagged in [None, b'wrong-head\n']:
            def git(*args):
                return b'head\n' if args == ('rev-parse', 'HEAD') else tagged
            with self.subTest(tagged=tagged), mock.patch.object(pipeline, 'git', side_effect=git):
                rendered = pipeline.qbit_template(self.config(manifest), '', 'publish-test')
                self.assertIn('qqq-orb/mvn_test_only', rendered['workflows']['test_only']['jobs'][0])

    def test_feature_tag_recovery_checks_fetched_commit(self):
        manifest = {'profile': 'qbit', 'orb_version': '0.7.16', 'default_branch': 'main', 'publish': {'feature': True}}
        with mock.patch.object(pipeline, 'git', side_effect=[None, b'', b'head\n', b'head\n']):
            rendered = pipeline.qbit_template(self.config(manifest), '', 'publish-test')
        self.assertEqual('feature', rendered['workflows']['publish_feature']['jobs'][0]['qqq-orb/mvn_publish']['branch_type'])

    def test_setup_preserves_release_policy_and_rejects_drift(self):
        for policy in ['stable', 'v-prefix', 'none']:
            manifest = {'profile': 'qbit', 'orb_version': '0.7.16', 'default_branch': 'main',
                        'release_tag_policy': policy, 'publish': {'feature': True}}
            caller = migration.canonical_caller('0.7.16', policy, True)
            standard.validate(yaml.safe_dump(caller), yaml.safe_dump(manifest), '0.7.16')
            self.assertEqual(caller, standard.canonical_caller('qbit', '0.7.16', release_tag_policy=policy, publish_feature=True))
            with self.assertRaises(standard.StandardError):
                standard.validate(yaml.safe_dump(migration.canonical_caller('0.7.16', policy)), yaml.safe_dump(manifest), '0.7.16')

    def test_unrecognized_feature_branch_filters_are_rejected(self):
        for branches in [{'only': ['/feature/.*/']}, {'only': ['main']}, {'ignore': '/.*/'}]:
            with self.subTest(branches=branches), self.assertRaises(ValueError):
                migration.publication_filters('feature', {'branches': branches, 'tags': {'only': ['/publish.*/']}})


if __name__ == '__main__':
    unittest.main()
