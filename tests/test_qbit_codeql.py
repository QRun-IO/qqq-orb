import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import yaml

ROOT = Path(__file__).parents[1]

class BranchLanguages(unittest.TestCase):
    def select(self, tracked, untracked=()):
        worker = yaml.safe_load((ROOT / '.github/workflows/qbit-codeql.yml').read_text())
        script = next(s['run'] for s in worker['jobs']['analyze']['steps'] if s.get('id') == 'languages')
        script = script.split("python3 <<'PY'\n", 1)[1].rsplit('\nPY', 1)[0]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(['git', 'init', '-q', directory], check=True)
            for name in (*tracked, *untracked):
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('fixture')
            if tracked:
                subprocess.run(['git', 'add', '--', *tracked], cwd=root, check=True)
            output = root / 'outputs'
            result = subprocess.run([sys.executable, '-c', script], cwd=root,
                                    env={**os.environ, 'GITHUB_OUTPUT': str(output)}, capture_output=True, text=True)
            return result, output.read_text() if output.exists() else ''

    def test_historical_java_branch_does_not_scan_absent_actions(self):
        result, output = self.select(['src/Example.java'])
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn('languages=java-kotlin\n', output)
        self.assertIn('build-mode=none\n', output)

    def test_current_branch_preserves_all_present_supported_languages(self):
        result, output = self.select(['src/Example.java', '.github/workflows/ci.yaml', 'web/app.tsx', 'tools/check.py'])
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn('languages=java-kotlin,javascript-typescript,python,actions\n', output)

    def test_kotlin_requires_a_build(self):
        result, output = self.select(['src/Example.kt', '.github/workflows/ci.yml'])
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn('build-mode=autobuild\n', output)

    def test_java_cli_preserves_homebrew_ruby_coverage(self):
        result, output = self.select(['src/Main.java', 'packaging/homebrew/qctl.rb', '.github/workflows/build.yml'])
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn('languages=java-kotlin,ruby,actions\n', output)
        self.assertIn('build-mode=none\n', output)

    def test_ruby_only_source_is_supported(self):
        result, output = self.select(['Formula/qctl.rb'])
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn('languages=ruby\n', output)
        self.assertIn('build-mode=none\n', output)

    def test_untracked_files_do_not_select_languages(self):
        result, output = self.select(['src/Example.java'], ['web/generated.js', 'generated/formula.rb', '.github/workflows/untracked.yml'])
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn('languages=java-kotlin\n', output)

    def test_placeholder_fails_explicitly(self):
        result, output = self.select(['README.md'])
        self.assertNotEqual(0, result.returncode)
        self.assertIn('No supported source', result.stderr)

if __name__ == '__main__':
    unittest.main()
