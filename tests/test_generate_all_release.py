import importlib.util
import json
from pathlib import Path
import unittest
import yaml

ROOT = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location('aux', ROOT / 'src/scripts/generate_auxiliary_workflow.py')
aux = importlib.util.module_from_spec(spec)
spec.loader.exec_module(aux)


class AllReleaseCallerTests(unittest.TestCase):
    def setUp(self):
        self.original = json.loads((ROOT / 'tests/fixtures/all-release-caller-original.json').read_text())
        self.caller = aux.canonical('all-release', 'a' * 40)
        self.worker = yaml.safe_load((ROOT / '.github/workflows/qqq-all-release.yml').read_text())
        self.contract = self.worker.get('on', self.worker.get(True))['workflow_call']

    def test_same_manual_only_path_version_choices_and_release_sha(self):
        self.assertEqual('.github/workflows/release.yml', aux.BRIDGES['all-release']['path'])
        self.assertEqual(self.original['name'], self.caller['name'])
        self.assertEqual({'workflow_dispatch'}, set(self.caller['on']))
        old = self.original['events']['workflow_dispatch']['inputs']
        new = self.caller['on']['workflow_dispatch']['inputs']
        for key in ('version', 'release_sha'):
            self.assertEqual(old[key], new[key])
        self.assertEqual(['4.1.0', '4.1.0-RC.1'], new['version']['options'])

    def test_all_inputs_match_worker_and_conditional_evidence(self):
        inputs = self.caller['on']['workflow_dispatch']['inputs']
        passed = self.caller['jobs']['release']['with']
        self.assertEqual(set(self.contract['inputs']), set(inputs))
        self.assertEqual(set(inputs), set(passed))
        for name in inputs:
            self.assertEqual('${{ inputs.' + name + ' }}', passed[name])
            self.assertEqual('string', self.contract['inputs'][name]['type'])
        # Migrated consumers no longer own a separate GitHub Smoke workflow.
        self.assertEqual('circle', inputs['smoke_evidence']['default'])
        self.assertEqual(['github', 'circle'], inputs['smoke_evidence']['options'])
        self.assertFalse(inputs['smoke_run_id']['required'])
        self.assertFalse(inputs['circle_workflow_id']['required'])
        checks = self.worker['jobs']['release']['steps'][1]['run']
        self.assertIn('github) [[ "$SMOKE_RUN_ID" =~ ^[0-9]+$ ]]', checks)
        self.assertIn('[[ "$CIRCLE_WORKFLOW_ID" =~ ^[0-9a-f-]{36}$ ]]', checks)
        self.assertIn('test "$GITHUB_REF" = refs/heads/develop', checks)

    def test_permissions_secrets_approval_and_concurrency_remain_central(self):
        self.assertEqual({**self.original['permissions'], 'checks': 'read'}, self.caller['permissions'])
        self.assertEqual(self.worker['permissions'], self.caller['permissions'])
        self.assertEqual(self.original['environment'], self.worker['jobs']['release']['environment'])
        self.assertEqual(self.original['concurrency'], self.worker['concurrency'])
        self.assertNotIn('concurrency', self.caller)
        job = self.caller['jobs']['release']
        self.assertEqual({'uses', 'with', 'secrets'}, set(job))
        self.assertEqual({'CIRCLECI_TOKEN': '${{ secrets.CIRCLECI_TOKEN }}'}, job['secrets'])
        self.assertEqual({'CIRCLECI_TOKEN': {'required': False}}, self.contract['secrets'])

    def test_pin_immutable_and_no_local_dynamic_orchestration(self):
        self.assertEqual('QRun-IO/qqq-orb/.github/workflows/qqq-all-release.yml@' + 'a' * 40, self.caller['jobs']['release']['uses'])
        for ref in ('main', 'v1', 'a' * 39, 'a' * 40 + '\n', '${{ inputs.worker }}'):
            with self.subTest(ref=ref), self.assertRaises(ValueError):
                aux.canonical('all-release', ref)
        changed = aux.canonical('all-release', 'a' * 40)
        changed['jobs']['release']['with']['version'] = 'unsafe'
        self.assertEqual('${{ inputs.version }}', aux.canonical('all-release', 'a' * 40)['jobs']['release']['with']['version'])


if __name__ == '__main__':
    unittest.main()
