"""GitHub Packages auth stays a literal, host-scoped runtime reference."""
import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('pipeline', ROOT / 'src/scripts/generate_pipeline.py')
pipeline = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pipeline)


class NodeArtifactAuth(unittest.TestCase):
    def test_registry_configuration_uses_github_credential_without_embedding_it(self):
        config = {'node_version': '20.19', 'context': 'packages', 'npm_scopes': ['@nocode-js', '@qrunio'],
                  'artifact_path': 'dist/component.js', 'build_branches': ['develop']}
        command = pipeline.node_artifact_template(config, 'develop', '')['jobs']['node_artifact']['steps'][1]['run']['command']
        with tempfile.TemporaryDirectory() as directory:
            env = {**os.environ, 'GITHUB_TOKEN': 'github-fixture-secret', 'NPM_TOKEN': 'npm-fixture-secret'}
            result = subprocess.run(['bash', '-c', command], cwd=directory, env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            contents = (Path(directory) / '.npmrc').read_text()
            self.assertEqual(contents.splitlines(), ['registry=https://registry.npmjs.org/',
                '@nocode-js:registry=https://npm.pkg.github.com/', '@qrunio:registry=https://npm.pkg.github.com/',
                '//npm.pkg.github.com/:_authToken=${GITHUB_TOKEN}'])
            for value in ('github-fixture-secret', 'npm-fixture-secret'):
                self.assertNotIn(value, contents + result.stdout + result.stderr)
