import importlib.util
import pathlib
import unittest
import os
import subprocess
import sys
import tempfile
import yaml

spec = importlib.util.spec_from_file_location('qctl', pathlib.Path(__file__).parents[1] / 'src/scripts/generate_qctl_workflow.py')
generator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(generator)


class QctlBridgeTests(unittest.TestCase):
    def test_real_render_is_tiny_pinned_caller_with_original_triggers(self):
        text = generator.generate('a' * 40)
        parsed = yaml.safe_load(text)
        triggers = parsed.get('on', parsed.get(True))
        self.assertEqual(['main', 'develop'], triggers['push']['branches'])
        self.assertEqual(['v*'], triggers['push']['tags'])
        self.assertEqual(['main', 'develop'], triggers['pull_request']['branches'])
        self.assertFalse(triggers['workflow_dispatch']['inputs']['full_native']['default'])
        self.assertEqual(['native'], list(parsed['jobs']))
        job = parsed['jobs']['native']
        self.assertEqual('QRun-IO/qqq-orb/.github/workflows/qctl-native.yml@' + 'a'*40, job['uses'])
        self.assertNotIn('steps', job)
        self.assertNotIn('runs-on', job)
        self.assertEqual('inherit', job['secrets'])

    def test_cli_detects_caller_drift(self):
        with tempfile.TemporaryDirectory() as directory:
            target = pathlib.Path(directory) / 'build.yml'
            target.write_text(generator.generate('a' * 40))
            command = [sys.executable, '-B', str(pathlib.Path(generator.__file__)), '--check', str(target)]
            environment = dict(os.environ, QCTL_SHARED_REF='a' * 40)
            self.assertEqual(0, subprocess.run(command, env=environment, capture_output=True).returncode)
            target.write_text(target.read_text().replace('secrets: inherit', 'secrets: {}'))
            result = subprocess.run(command, env=environment, capture_output=True, text=True)
            self.assertNotEqual(0, result.returncode)
            self.assertIn('differs from canonical', result.stderr)

    def test_mutable_or_injected_worker_reference_rejected(self):
        for ref in ['main', 'v1.0.0', '', 'a'*40 + '\nsteps:', '${{ secrets.TOKEN }}']:
            with self.subTest(ref=ref), self.assertRaises(ValueError):
                generator.generate(ref)


if __name__ == '__main__': unittest.main()
