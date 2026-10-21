"""CI maintenance retains Maven verification and never becomes a release request."""
import importlib.util
from pathlib import Path
import unittest
from unittest import mock
import yaml

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('pipeline', ROOT/'src/scripts/generate_pipeline.py')
pipeline = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pipeline)


class MaintenanceTests(unittest.TestCase):
    def git_result(self, *args):
        return {'log': self.subject, 'rev-list': self.parents, 'diff': self.paths}.get(args[0])

    def setUp(self):
        self.subject = b'ci: use central pipeline\n'
        self.parents = b'a'*40 + b' ' + b'b'*40 + b'\n'
        self.paths = b'.qqq-ci.yml\0.circleci/config.yml\0.github/workflows/codeql.yml\0.github/workflows/release-rc.yml\0'

    def test_publishing_branches_keep_unfiltered_maven_tests(self):
        manifest = {'profile': 'qbit', 'orb_version': '0.7.14', 'default_branch': 'develop',
                    'release_on_main': True, 'test_branch_policy': 'feature-no-hotfix',
                    'publish': {'hotfix': True}}
        with mock.patch.object(Path, 'read_text', return_value=yaml.safe_dump(manifest)):
            config = pipeline.load_manifest('unused', '0.7.14')
        with mock.patch.object(pipeline, 'git', side_effect=self.git_result):
            for branch in ('main', 'develop', 'release/0.1', 'hotfix/1.2.3'):
                with self.subTest(branch=branch):
                    result = pipeline.qbit_template(config, branch, '')
                    job = result['workflows']['test_only']['jobs'][0]['qqq-orb/mvn_test_only']
                    self.assertEqual(job['filters']['branches'], {'ignore': 'automation/qbit-rc-pending'})
                    self.assertNotIn('branch_type', job)

    def test_nonpublishing_branches_verify_maintenance_but_keep_application_policy(self):
        manifest = {'profile': 'qbit', 'orb_version': '0.8', 'default_branch': 'main',
                    'release_on_main': False, 'test_branch_policy': 'feature-no-hotfix',
                    'publish': {'snapshot': False, 'release_candidate': False, 'hotfix': False}}
        with mock.patch.object(Path, 'read_text', return_value=yaml.safe_dump(manifest)):
            config = pipeline.load_manifest('unused', '0.8')
        maintenance_paths = self.paths
        with mock.patch.object(pipeline, 'git', side_effect=self.git_result):
            for branch in ('main', 'develop', 'release/0.1', 'hotfix/1.2.3'):
                for maintenance in (True, False):
                    with self.subTest(branch=branch, maintenance=maintenance):
                        self.paths = maintenance_paths if maintenance else b'src/Main.java\0'
                        result = pipeline.qbit_template(config, branch, '')
                        job = result['workflows']['test_only']['jobs'][0]['qqq-orb/mvn_test_only']
                        ignored = job['filters']['branches']['ignore']
                        if maintenance:
                            self.assertEqual(ignored, 'automation/qbit-rc-pending')
                        else:
                            self.assertEqual(ignored, ['automation/qbit-rc-pending',
                                '/(develop|main|release/.*|hotfix/.*|integration.*)/'])
                        self.assertNotIn('branch_type', job)

    def test_frontend_maintenance_verifies_without_publishing(self):
        for profile, prefix in (('frontend-core', 'node_'), ('frontend-material', 'mvn_frontend_')):
            manifest = {'profile': profile, 'orb_version': '0.8', 'default_branch': 'develop'}
            with mock.patch.object(Path, 'read_text', return_value=yaml.safe_dump(manifest)):
                config = pipeline.load_manifest('unused', '0.8')
            for branch in ('main', 'develop', 'release/1.0', 'hotfix/1.0.1'):
                with self.subTest(profile=profile, branch=branch), mock.patch.object(pipeline, 'git', side_effect=self.git_result):
                    result = pipeline.frontend_template(config, branch, '')
                    job = result['workflows']['test_only']['jobs'][0]['qqq-orb/' + prefix + 'test_only']
                    self.assertNotIn('branch_type', job)
                    self.assertEqual(job['filters']['branches'], {'ignore': 'automation/qbit-rc-pending'})
            self.paths = b'package.json\0'
            with mock.patch.object(pipeline, 'git', side_effect=self.git_result):
                result = pipeline.frontend_template(config, 'develop', '')
                self.assertIn('qqq-orb/' + prefix + 'publish', result['workflows']['publish_snapshot']['jobs'][0])
            self.paths = b'.qqq-ci.yml\0'
            with mock.patch.object(pipeline, 'git', return_value=b'verified-head\n'):
                result = pipeline.frontend_template(config, 'main', 'v1.2.3')
                job = result['workflows']['publish_release']['jobs'][0]['qqq-orb/' + prefix + 'publish']
                self.assertEqual(job['branch_type'], 'release')

    def test_application_changes_and_unknown_files_publish_normally(self):
        for paths in (b'pom.xml\0', b'.qqq-ci.yml\0src/Main.java\0', b'.github/workflows/custom-release.yml\0', b'', None):
            self.paths = paths
            with mock.patch.object(pipeline, 'git', side_effect=self.git_result):
                self.assertFalse(pipeline.proven_ci_maintenance('release/0.1', ''))

    def test_schema_caller_migration_is_maintenance_but_schema_inputs_are_not(self):
        self.paths = b'.github/workflows/schema-drift.yml\0'
        with mock.patch.object(pipeline, 'git', side_effect=self.git_result):
            self.assertTrue(pipeline.proven_ci_maintenance('release/0.1', ''))
            for path in (b'pom.xml\0', b'src/test/resources/schema.yml\0', b'src/test/java/SchemaDriftTest.java\0'):
                self.paths = b'.github/workflows/schema-drift.yml\0' + path
                self.assertFalse(pipeline.proven_ci_maintenance('release/0.1', ''))

    def test_merge_root_and_unavailable_history_do_not_suppress_release(self):
        for parents in (None, b'a'*40+b'\n', self.parents.rstrip()+b' '+b'c'*40+b'\n'):
            self.parents = parents
            with mock.patch.object(pipeline, 'git', side_effect=self.git_result):
                self.assertFalse(pipeline.proven_ci_maintenance('release/0.1', ''))

    def test_tags_and_release_requests_do_not_suppress_release(self):
        with mock.patch.object(pipeline, 'git', side_effect=self.git_result):
            self.assertFalse(pipeline.proven_ci_maintenance('main', 'v1.2.3'))
            for subject in (b'Merge develop for next RC\n', b'fix: application\n', None):
                self.subject = subject
                self.assertFalse(pipeline.proven_ci_maintenance('release/0.1', ''))


if __name__ == '__main__':
    unittest.main()
