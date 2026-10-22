"""Central execution rejects untrusted branches and preserves partial evidence."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import run_enrollment


class RunnerTests(unittest.TestCase):
    def environment(self):
        return {'CIRCLE_PROJECT_USERNAME': 'QRun-IO', 'CIRCLE_PROJECT_REPONAME': 'qqq-orb',
                'CIRCLE_BRANCH': 'main', 'GITHUB_TOKEN': 'test-only-secret'}

    def test_wrong_owner_branch_repo_tag_or_missing_auth_cannot_execute(self):
        for change in ({'CIRCLE_PROJECT_USERNAME': 'other'}, {'CIRCLE_PROJECT_REPONAME': 'other'},
                       {'CIRCLE_BRANCH': 'develop'}, {'CIRCLE_TAG': 'v1.0.0'}, {'GITHUB_TOKEN': ''}):
            execute = Mock()
            with self.subTest(change=change), self.assertRaises(ValueError):
                run_enrollment.run({**self.environment(), **change}, execute)
            execute.assert_not_called()

    def test_timeout_retains_partial_report_without_secrets(self):
        with tempfile.TemporaryDirectory() as directory:
            def execute(args, **kwargs):
                output = Path(args[args.index('--output') + 1])
                output.write_text('[{"state":"unresolved"}]')
                self.assertEqual(1200, kwargs['timeout'])
                self.assertEqual('test-only-secret', kwargs['env']['GH_TOKEN'])
                raise subprocess.TimeoutExpired(args, 1200)
            self.assertEqual(124, run_enrollment.run(self.environment(), execute, directory))
            output = Path(directory) / 'artifacts/enrollment'
            self.assertEqual([{'state': 'unresolved'}], json.loads((output / 'result.json').read_text()))
            self.assertEqual('timed-out', json.loads((output / 'run.json').read_text())['state'])
            self.assertNotIn('test-only-secret', (output / 'run.json').read_text())

    def test_failed_pass_propagates_nonzero_exit(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(2, run_enrollment.run(self.environment(), Mock(return_value=Mock(returncode=2)), directory))
            self.assertEqual('failed', json.loads((Path(directory) / 'artifacts/enrollment/run.json').read_text())['state'])


if __name__ == '__main__':
    unittest.main()
