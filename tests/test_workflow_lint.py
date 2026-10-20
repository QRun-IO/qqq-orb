import importlib.util
from pathlib import Path
import unittest
import yaml

ROOT = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location('bridge', ROOT / 'src/scripts/generate_auxiliary_workflow.py')
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)


class WorkflowLintTests(unittest.TestCase):
    def test_original_actionlint_image_version_and_all_yml_scope_preserved(self):
        worker = yaml.safe_load((ROOT / '.github/workflows/workflow-lint.yml').read_text())
        self.assertEqual({'workflow_call': None}, worker['on'])
        self.assertEqual({'contents': 'read'}, worker['permissions'])
        self.assertEqual({'actionlint'}, set(worker['jobs']))
        job = worker['jobs']['actionlint']
        self.assertEqual('cimg/go:1.24', job['container'])
        self.assertEqual('actions/checkout@v4', job['steps'][0]['uses'])
        self.assertEqual(['go run github.com/rhysd/actionlint/cmd/actionlint@v1.7.7 -color .github/workflows/*.yml'], [s['run'] for s in job['steps'] if 'run' in s])

    def test_tiny_immutable_bridge_no_tag_or_same_repo_pr_duplicate(self):
        caller = bridge.canonical('github-workflow-lint', 'a' * 40)
        self.assertEqual({'branches': ['**']}, caller['on']['push'])
        self.assertIn('pull_request', caller['on'])
        self.assertEqual({'contents': 'read'}, caller['permissions'])
        job = caller['jobs']['actionlint']
        self.assertEqual("github.event_name != 'pull_request' || github.event.pull_request.head.repo.full_name != github.repository", job['if'])
        self.assertEqual('QRun-IO/qqq-orb/.github/workflows/workflow-lint.yml@' + 'a' * 40, job['uses'])
        self.assertNotIn('steps', job)
        self.assertNotIn('secrets', job)
        with self.assertRaises(ValueError):
            bridge.canonical('github-workflow-lint', 'main')


if __name__ == '__main__':
    unittest.main()
