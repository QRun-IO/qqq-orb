import importlib.util
import os
from pathlib import Path
import unittest
from unittest.mock import patch
import yaml

ROOT = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location('bridge', ROOT / 'src/scripts/generate_auxiliary_workflow.py')
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)
WORKER = yaml.safe_load((ROOT / '.github/workflows/intellij-plugin.yml').read_text())


class IntelliJTests(unittest.TestCase):
    def test_real_wrapper_build_and_distribution_retained(self):
        build = WORKER['jobs']['build']
        self.assertNotIn('if', build)
        self.assertIn('./gradlew --no-daemon check buildPlugin', [s.get('run') for s in build['steps']])
        java = next(s for s in build['steps'] if s.get('uses') == 'actions/setup-java@v4')
        self.assertEqual('17', java['with']['java-version'])
        upload = next(s for s in build['steps'] if s.get('with', {}).get('path') == 'build/distributions/*.zip')
        self.assertEqual('error', upload['with']['if-no-files-found'])
        self.assertNotIn('secrets.', str(build))

    def test_release_is_manual_after_build_protected_serial_and_signed(self):
        job = WORKER['jobs']['publish']
        self.assertEqual('build', job['needs'])
        self.assertEqual("github.event_name == 'workflow_dispatch' && inputs.publish", job['if'])
        self.assertEqual('intellij-marketplace', job['environment'])
        self.assertFalse(job['concurrency']['cancel-in-progress'])
        step = next(s for s in job['steps'] if s.get('name') == 'Sign and publish verified plugin')
        self.assertEqual({'CERTIFICATE_CHAIN', 'PRIVATE_KEY', 'PRIVATE_KEY_PASSWORD', 'PUBLISH_TOKEN'}, set(step['env']))
        for key in step['env']: self.assertIn('test -n "$' + key + '"', step['run'])
        self.assertIn('./gradlew --no-daemon signPlugin publishPlugin', step['run'])

    def test_actual_inline_version_guard_rejects_wrong_tag_version_and_injection(self):
        step = next(s for s in WORKER['jobs']['publish']['steps'] if s.get('name') == 'Verify exact reviewed version and tag')
        code = step['run'].split("<<'PY'\n", 1)[1].split('\nPY', 1)[0]
        for version, tag, source, allowed in [('1.1.0', 'refs/tags/v1.1.0', '1.1.0', True),
             ('1.1.0', 'refs/heads/main', '1.1.0', False), ('1.1.0', 'refs/tags/v1.1.0', '1.2.0', False),
             ('1.1.0;echo secret', 'refs/tags/v1.1.0', '1.1.0', False)]:
            with patch.dict(os.environ, RELEASE_VERSION=version, GITHUB_REF=tag), patch.object(Path, 'read_text', return_value='version = "' + source + '"'):
                if allowed: exec(code, {})
                else:
                    with self.assertRaises(SystemExit): exec(code, {})
        self.assertIn('git ls-remote origin', step['run'])
        self.assertIn('test "$resolved" = "$GITHUB_SHA"', step['run'])

    def test_tiny_bridge_keeps_publication_opt_in_and_immutable_worker(self):
        caller = bridge.canonical('intellij-plugin', 'a'*40)
        self.assertFalse(caller['on']['workflow_dispatch']['inputs']['publish']['default'])
        self.assertIn('pull_request', caller['on'])
        self.assertEqual(1, len(caller['jobs']))
        self.assertNotIn('steps', caller['jobs']['plugin'])
        self.assertTrue(caller['jobs']['plugin']['uses'].endswith('@' + 'a'*40))


if __name__ == '__main__': unittest.main()
