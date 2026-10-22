#!/usr/bin/env python3
"""Exercise the actual version calculator before any Maven mutation."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

class VersionPreflightTests(unittest.TestCase):
    def calculate(self, version, branch, dry_run=True):
        with tempfile.TemporaryDirectory() as scratch:
            folder = Path(scratch)
            pom = folder / 'pom.xml'
            original = f'<project><revision>{version}</revision></project>\n'
            pom.write_text(original)
            for name, body in (('git', 'echo abc1234'), ('mvn', 'echo invoked >> "$PWD/maven-called"; exit 99')):
                command = folder / name
                command.write_text('#!/bin/sh\n' + body + '\n')
                command.chmod(0o755)
            env = dict(os.environ, CIRCLE_BRANCH=branch, PATH=str(folder) + os.pathsep + os.environ['PATH'])
            result = subprocess.run(['bash', str(ROOT / 'src/scripts/calculate_version.sh')]
                                    + (['--dry-run'] if dry_run else []),
                                    cwd=folder, env=env, text=True, capture_output=True, timeout=10)
            self.assertEqual(pom.read_text(), original)
            self.assertFalse((folder / 'maven-called').exists())
            return result

    def test_generated_boundary_and_original_failure(self):
        for size in (49, 50, 51):
            with self.subTest(size=size):
                result = self.calculate('1.2.3-SNAPSHOT', 'feature/' + 'a' * (size - 23))
                self.assertEqual(result.returncode, 0 if size <= 50 else 1, result.stdout + result.stderr)
                if size > 50:
                    self.assertIn('51 characters', result.stderr)
                    self.assertIn('at most 50', result.stderr)
        result = self.calculate('4.1.0-SNAPSHOT', 'feature/collaboration-production-20261021', False)
        self.assertEqual(result.returncode, 1)
        self.assertIn('Use a shorter feature branch', result.stderr)

    def test_existing_oversized_version(self):
        result = self.calculate('1.2.3-' + 'b' * 28 + '-abc1234-SNAPSHOT', 'maintenance/check', False)
        self.assertEqual(result.returncode, 1)
        self.assertIn('51 characters', result.stderr)

    def test_candidate_coordinates_unchanged(self):
        for version in ('4.1.0-collab-33464d37e-SNAPSHOT', '0.1.0-collab-8f348da-SNAPSHOT',
                        '0.1.0-redis-7fe5492-SNAPSHOT', '0.1.0-session-b5276ab-SNAPSHOT', '1.0.0-RC.37'):
            with self.subTest(version=version):
                result = self.calculate(version, 'maintenance/check')
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn('Calculated next version: ' + version, result.stdout)

if __name__ == '__main__':
    unittest.main()
