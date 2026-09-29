#!/usr/bin/env python3
"""Exercise publisher boundaries without network access or real credentials."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'src/scripts/node_npm_publish.sh'
NODE = shutil.which('node')
NPM = shutil.which('npm')


class PublishTests(unittest.TestCase):
    def run_publish(self, version='1.0.0-RC.1', trusted=True, project_config=False, trusted_mode=None, **overrides):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bin_dir = root / 'bin'
            bin_dir.mkdir()
            (root / 'package.json').write_text(json.dumps({'version': version}) + '\n')
            if project_config:
                (root / '.npmrc').write_text('//registry.npmjs.org/:_authToken=synthetic-old-token\n')
            scripts = {
                'npm': '''#!/usr/bin/env python3
import json, os, pathlib, subprocess, sys
if sys.argv[1:] == ['--version']:
    print(os.environ.get('TEST_NPM_VERSION', '11.19.0'))
else:
    assert sys.argv[1] == 'publish', 'Unexpected npm command'
    if os.environ['QQQ_NPM_TRUSTED_PUBLISHING'] in ['true', '1']:
        assert os.environ.get('NPM_ID_TOKEN') == 'synthetic-oidc-token'
        assert all(not os.environ.get(name) for name in ['NPM_TOKEN', 'NODE_AUTH_TOKEN', 'NPM_AUTH_TOKEN'])
        assert os.environ['NPM_CONFIG_USERCONFIG'] != os.environ['NPM_CONFIG_GLOBALCONFIG']
        assert not pathlib.Path(os.environ['NPM_CONFIG_USERCONFIG']).exists()
        assert not pathlib.Path(os.environ['NPM_CONFIG_GLOBALCONFIG']).exists()
        registry = subprocess.check_output([os.environ['TEST_REAL_NPM'], 'config', 'get', 'registry'], text=True)
        assert registry.strip() == 'https://registry.npmjs.org/'
    pathlib.Path('published.json').write_text(json.dumps(sys.argv[1:]))
    sys.exit(int(os.environ.get('TEST_PUBLISH_STATUS', '0')))
''',
                'circleci': '''#!/usr/bin/env python3
import os, pathlib, sys
assert sys.argv[1:] == ['run', 'oidc', 'get', '--claims', '{"aud":"npm:registry.npmjs.org"}']
pathlib.Path('oidc-called').touch()
print(os.environ.get('TEST_OIDC_VALUE', 'synthetic-oidc-token'))
sys.exit(int(os.environ.get('TEST_OIDC_STATUS', '0')))
''',
                'node': '''#!/usr/bin/env python3
import os, subprocess, sys
if sys.argv[1] != '-':
    os.execv(os.environ['TEST_REAL_NODE'], [os.environ['TEST_REAL_NODE'], *sys.argv[1:]])
source = sys.stdin.read()
if 'TEST_NODE_VERSION' in os.environ:
    source = source.replace('process.versions.node', repr(os.environ['TEST_NODE_VERSION']))
sys.exit(subprocess.run([os.environ['TEST_REAL_NODE'], *sys.argv[1:]], input=source, text=True).returncode)
'''
            }
            for name, contents in scripts.items():
                executable = bin_dir / name
                executable.write_text(contents)
                executable.chmod(0o755)
            env = dict(os.environ, PATH=str(bin_dir) + os.pathsep + os.environ['PATH'],
                       QQQ_NPM_TRUSTED_PUBLISHING=str(trusted).lower() if trusted_mode is None else trusted_mode,
                       TEST_REAL_NODE=NODE, TEST_REAL_NPM=NPM,
                       NPM_TOKEN='synthetic-old-token', NODE_AUTH_TOKEN='synthetic-old-token',
                       NPM_AUTH_TOKEN='synthetic-old-token', **overrides)
            result = subprocess.run(['bash', '-x', str(SCRIPT)], cwd=root, env=env,
                                    text=True, capture_output=True)
            self.assertNotIn('synthetic-oidc-token', result.stdout + result.stderr)
            self.assertNotIn('synthetic-old-token', result.stdout + result.stderr)
            published = root / 'published.json'
            return result, json.loads(published.read_text()) if published.exists() else None, (root / 'oidc-called').exists()

    def test_tags_and_legacy_authentication(self):
        for trusted in [True, False]:
            for version, tag in [('1.0.0-RC.1', 'rc'), ('1.0.0-SNAPSHOT', 'snapshot'),
                                 ('1.0.0-alpha.1', 'next'), ('1.0.0-beta.1', 'next'), ('1.0.0', 'latest')]:
                with self.subTest(trusted=trusted, version=version):
                    result, args, oidc = self.run_publish(version, trusted)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(args, ['publish', '--access', 'public', '--tag', tag])
                    self.assertEqual(oidc, trusted)

    def test_circleci_boolean_environment_values(self):
        for mode, expected_oidc in [('1', True), ('0', False)]:
            with self.subTest(mode=mode):
                result, args, oidc = self.run_publish(trusted_mode=mode)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(args, ['publish', '--access', 'public', '--tag', 'rc'])
                self.assertEqual(oidc, expected_oidc)

    def test_oidc_failure_or_empty_token_stops_publication(self):
        for overrides in [{'TEST_OIDC_STATUS': '7'}, {'TEST_OIDC_VALUE': ''}]:
            with self.subTest(overrides=overrides):
                result, args, oidc = self.run_publish(**overrides)
                self.assertNotEqual(result.returncode, 0)
                self.assertIsNone(args)
                self.assertTrue(oidc)

    def test_unsupported_toolchains_stop_before_requesting_identity(self):
        for overrides in [{'TEST_NPM_VERSION': '11.5.0'}, {'TEST_NPM_VERSION': '10.9.0'},
                          {'TEST_NODE_VERSION': '22.13.1'}, {'TEST_NODE_VERSION': '20.20.0'}]:
            with self.subTest(overrides=overrides):
                result, args, oidc = self.run_publish(**overrides)
                self.assertNotEqual(result.returncode, 0)
                self.assertIsNone(args)
                self.assertFalse(oidc)

    def test_minimum_toolchain_is_supported(self):
        result, args, oidc = self.run_publish(TEST_NPM_VERSION='11.5.1', TEST_NODE_VERSION='22.14.0')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIsNotNone(args)
        self.assertTrue(oidc)

    def test_project_or_environment_credentials_are_rejected(self):
        for overrides in [{'project_config': True}, {'NPM_CONFIG__AUTH': 'synthetic-old-token'},
                          {'npm_config_userconfig': '/synthetic/legacy.npmrc'},
                          {'npm_config_USERCONFIG': '/synthetic/legacy.npmrc'},
                          {'Npm_Config_Globalconfig': '/synthetic/legacy.npmrc'}]:
            with self.subTest(overrides=overrides):
                result, args, oidc = self.run_publish(**overrides)
                self.assertNotEqual(result.returncode, 0)
                self.assertIsNone(args)
                self.assertFalse(oidc)

    def test_publish_failure_is_not_reported_as_success(self):
        result, args, oidc = self.run_publish(TEST_PUBLISH_STATUS='9')
        self.assertEqual(result.returncode, 9)
        self.assertIsNotNone(args)
        self.assertTrue(oidc)
        self.assertNotIn('Successfully published', result.stdout)


if __name__ == '__main__':
    unittest.main()
