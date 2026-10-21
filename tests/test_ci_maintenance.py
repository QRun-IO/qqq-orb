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
        self.paths = b'.qqq-ci.yml\0.circleci/config.yml\0.github/workflows/codeql.yml\0'

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

    def test_application_changes_and_unknown_files_publish_normally(self):
        for paths in (b'pom.xml\0', b'.qqq-ci.yml\0src/Main.java\0', b'.github/workflows/release-rc.yml\0', b'', None):
            self.paths = paths
            with mock.patch.object(pipeline, 'git', side_effect=self.git_result):
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
