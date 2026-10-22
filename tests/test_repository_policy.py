"""Execute the policy job against real git indexes, including application promotion."""
import importlib.util
import json
import os
import shutil
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import yaml

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('pipeline', ROOT / 'src/scripts/generate_pipeline.py')
pipeline = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pipeline)
TEMPLATE = json.loads((ROOT / 'src/scripts/templates/repository-policy.json').read_text())
SCRIPT = TEMPLATE['jobs']['validate-policy']['steps'][-1]['run']['command'].split("<<'PYTHON'\n", 1)[1].rsplit('PYTHON', 1)[0]


class RepositoryPolicyTests(unittest.TestCase):
    def test_packing_is_independent_of_checkout_line_endings(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copytree(ROOT / 'src/scripts', root / 'src/scripts')
            (root / 'scripts').mkdir()
            shutil.copy(ROOT / 'scripts/pack_pipeline.py', root / 'scripts/pack_pipeline.py')
            resources = list((root / 'src/scripts/templates').glob('*.json'))
            for resource in resources:
                resource.write_bytes(resource.read_bytes().replace(b'\r\n', b'\n'))
            subprocess.run([sys.executable, str(root / 'scripts/pack_pipeline.py')], check=True)
            packed = (root / 'src/scripts/packed_generate_pipeline.py').read_bytes()
            for resource in resources:
                resource.write_bytes(resource.read_bytes().replace(b'\n', b'\r\n'))
            subprocess.run([sys.executable, str(root / 'scripts/pack_pipeline.py'), '--check'], check=True)
            self.assertEqual(packed, (root / 'src/scripts/packed_generate_pipeline.py').read_bytes())

    def execute(self, files, untracked=None, shell_checks=False):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(['git', 'init', '-q'], cwd=root, check=True)
            for name, content in files.items():
                file = root / name
                file.parent.mkdir(parents=True, exist_ok=True)
                file.write_text(content, encoding='utf-8')
            subprocess.run(['git', 'add', '.'], cwd=root, check=True)
            for name, content in (untracked or {}).items():
                (root / name).write_text(content, encoding='utf-8')
            env = dict(os.environ, QQQ_POLICY_SHELL='true' if shell_checks else 'false')
            return subprocess.run([sys.executable, '-c', SCRIPT], cwd=root, env=env, capture_output=True, text=True)

    def test_placeholder_with_wrappers_and_workflows(self):
        result = self.execute({'LICENSE': 'Apache-2.0', 'docs/DESIGN.md': '# Planned application',
                               '.github/workflows/release-rc.yml': 'name: Release\non: workflow_dispatch\n',
                               '.mvn/wrapper/maven-wrapper.properties': 'distributionUrl=https://example.invalid/maven.zip',
                               'mvnw': '#!/bin/sh\n', 'mvnw.cmd': '@echo off\n'})
        self.assertEqual(0, result.returncode, result.stderr)

    def test_new_application_requires_real_build_profile(self):
        for name in ('pom.xml', 'package.json', 'src/App.java', 'main.py', 'main.go', 'Dockerfile'):
            with self.subTest(name=name):
                self.assertNotEqual(0, self.execute({'LICENSE': 'license', name: '{}'}).returncode)

    def test_malformed_configuration_fails(self):
        for name in ('.github/dependabot.yml', 'settings.json'):
            with self.subTest(name=name):
                self.assertNotEqual(0, self.execute({name: '[unterminated'}).returncode)

    def test_unused_checkstyle_policy_is_validated_without_allowing_application_xml(self):
        self.assertEqual(0, self.execute({'checkstyle/config.xml': '<module name="Checker"/>'}).returncode)
        self.assertNotEqual(0, self.execute({'checkstyle/config.xml': '<module>'}).returncode)
        self.assertNotEqual(0, self.execute({'application.xml': '<application/>'}).returncode)
        self.assertNotEqual(0, self.execute({'pom.xml': '<project/>'}).returncode)

    def test_only_tracked_files_are_policy_inputs(self):
        self.assertEqual(0, self.execute({'README.md': '# Docs'}, {'main.py': 'temporary tool'}).returncode)

    def test_shell_validation_is_opt_in_and_never_executes_scripts(self):
        files = {'automation/safe.sh': '#!/bin/bash\nexit 42\n', 'diagram.mmd': 'flowchart LR\n A-->B\n'}
        self.assertNotEqual(0, self.execute(files).returncode)
        result = self.execute(files, shell_checks=True)
        self.assertEqual(0, result.returncode, result.stderr)

    def test_shell_validation_rejects_syntax_warnings_and_application_sources(self):
        for name, content in [('broken.sh', '#!/bin/bash\nif then\n'),
                              ('unsafe.sh', '#!/bin/bash\necho $unquoted\n'),
                              ('main.py', 'print(42)'), ('package.json', '{}')]:
            with self.subTest(name=name):
                self.assertNotEqual(0, self.execute({name: content}, shell_checks=True).returncode)

    def test_shell_option_is_strict_and_keeps_single_small_nonpublishing_job(self):
        manifest = {'profile': 'repository-policy', 'orb_version': '0.8',
                    'default_branch': 'main', 'shell_checks': True}
        with patch.object(Path, 'read_text', return_value=yaml.safe_dump(manifest)):
            config = pipeline.load_manifest('unused', '0.8')
        result = pipeline.repository_policy_template(config, 'main', '')
        self.assertFalse(any(config['publish'].values()))
        self.assertEqual({'validate-policy'}, set(result['jobs']))
        self.assertEqual('small', result['jobs']['validate-policy']['resource_class'])
        self.assertEqual({'QQQ_POLICY_SHELL': 'true'}, result['jobs']['validate-policy']['environment'])
        for overrides in ({'shell_checks': 'true'}, {'profile': 'qbit'}):
            with patch.object(Path, 'read_text', return_value=yaml.safe_dump(dict(manifest, **overrides))):
                with self.assertRaises(pipeline.ManifestError):
                    pipeline.load_manifest('unused', '0.8')

    def test_manifest_cannot_enable_publication(self):
        manifest = {'profile': 'repository-policy', 'orb_version': '0.7.14', 'default_branch': 'develop'}
        with patch.object(Path, 'read_text', return_value=yaml.safe_dump(manifest)):
            config = pipeline.load_manifest('unused', '0.7.14')
        self.assertFalse(any(config['publish'].values()))
        self.assertEqual({'verify': {'jobs': ['validate-policy']}}, pipeline.repository_policy_template(config, 'main', '')['workflows'])
        manifest['publish'] = {'release': True}
        with patch.object(Path, 'read_text', return_value=yaml.safe_dump(manifest)), self.assertRaises(pipeline.ManifestError):
            pipeline.load_manifest('unused', '0.7.14')


if __name__ == '__main__':
    unittest.main()
