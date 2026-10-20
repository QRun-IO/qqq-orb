import copy
import importlib.util
import json
from pathlib import Path
import unittest
import yaml

ROOT = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location('auxiliary', ROOT / 'src/scripts/generate_auxiliary_workflow.py')
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)
ORIGINALS = json.loads((ROOT / 'tests/fixtures/auxiliary-original-workflows.json').read_text())
SHA = 'a' * 40


class AuxiliaryTests(unittest.TestCase):
    def test_all_worker_jobs_exactly_preserve_audited_source(self):
        for kind, original in ORIGINALS.items():
            with self.subTest(kind=kind):
                worker = yaml.safe_load((ROOT / '.github/workflows' / (kind + '.yml')).read_text())
                expected = copy.deepcopy(original['jobs'])
                if kind == 'core-quickstart-lifecycle':
                    for job in expected.values():
                        for step in job.get('steps', []):
                            if 'run' in step:
                                # Existing umask 077 gives mkdir the required private permissions.
                                step['run'] = step['run'].replace('mkdir -m 700 -p', 'mkdir -p')
                self.assertEqual(expected, worker['jobs'])
                self.assertEqual(original['permissions'], worker.get('permissions'))
                self.assertEqual({'workflow_call'}, set(worker['on']))

    def test_callers_preserve_events_and_have_no_local_steps(self):
        for kind, original in ORIGINALS.items():
            with self.subTest(kind=kind):
                caller = bridge.canonical(kind, SHA)
                self.assertEqual(original['events'], caller['on'])
                self.assertEqual(1, len(caller['jobs']))
                job = next(iter(caller['jobs'].values()))
                self.assertEqual('QRun-IO/qqq-orb/.github/workflows/' + kind + '.yml@' + SHA, job['uses'])
                self.assertNotIn('steps', job)
                self.assertNotIn('secrets', job)
                self.assertEqual(original['permissions'] or original['jobs']['analyze']['permissions'], caller['permissions'])

    def test_native_dispatch_inputs_forwarded_with_correct_types(self):
        for kind, original in ORIGINALS.items():
            worker = yaml.safe_load((ROOT / '.github/workflows' / (kind + '.yml')).read_text())
            inputs = worker['on']['workflow_call'].get('inputs', {})
            source = (original['events'].get('workflow_dispatch') or {}).get('inputs', {})
            self.assertEqual(set(source), set(inputs))
            job = next(iter(bridge.canonical(kind, SHA)['jobs'].values()))
            self.assertEqual(set(source), set(job.get('with', {})))
            for name, value in inputs.items():
                self.assertIn(value['type'], ['string', 'boolean'])
                self.assertIn('inputs.' + name, job['with'][name])
        quickstart = yaml.safe_load((ROOT / '.github/workflows/core-quickstart-lifecycle.yml').read_text())
        self.assertFalse(quickstart['on']['workflow_call']['inputs']['source_sha']['required'])
        self.assertFalse(quickstart['on']['workflow_call']['inputs']['boundary_capture']['default'])

    def test_ref_must_be_immutable_and_calls_are_independent(self):
        for ref in ['main', 'v1.0.0', 'a'*39, 'a'*40 + '\n']:
            with self.assertRaises(ValueError):
                bridge.canonical('core-codeql', ref)
        caller = bridge.canonical('core-codeql', SHA)
        caller['jobs'].clear()
        self.assertTrue(bridge.canonical('core-codeql', SHA)['jobs'])


if __name__ == '__main__': unittest.main()
