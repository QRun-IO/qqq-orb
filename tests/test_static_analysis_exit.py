"""Maven failures must survive tee without overriding project analysis policy."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = [('mvn_spotbugs.sh', 'SPOTBUGS_FAIL_ON_ERROR', 'spotbugs.failOnError'),
           ('mvn_pmd.sh', 'PMD_FAIL_ON_VIOLATION', 'pmd.failOnViolation')]


class StaticAnalysisExitTests(unittest.TestCase):
    def invoke(self, script, variable, setting, status):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            binary = root / 'mvn'
            binary.write_text('#!/bin/sh\nprintf "%s\\n" "$@" > "$ARGUMENT_FILE"\necho analysis-output\nexit "$FAKE_MAVEN_EXIT"\n')
            binary.chmod(0o755)
            env = dict(os.environ, PATH=str(root) + os.pathsep + os.environ['PATH'],
                       ARGUMENT_FILE=str(root / 'arguments'), FAKE_MAVEN_EXIT=str(status))
            env.pop(variable, None)
            if setting is not None:
                env[variable] = setting
            result = subprocess.run(['bash', str(ROOT / 'src/scripts' / script)], cwd=root,
                                    env=env, text=True, capture_output=True, timeout=15)
            return result, (root / 'arguments').read_text().splitlines()

    def test_maven_failure_is_never_hidden_by_successful_tee(self):
        for script, variable, _ in SCRIPTS:
            for setting in ('true', 'false'):
                with self.subTest(script=script, setting=setting):
                    result, _ = self.invoke(script, variable, setting, 17)
                    self.assertEqual(17, result.returncode)
                    self.assertIn('analysis-output', result.stdout)

    def test_success_preserves_explicit_flag_and_project_defaults(self):
        for script, variable, property_name in SCRIPTS:
            for setting in ('true', 'false', None):
                with self.subTest(script=script, setting=setting):
                    result, arguments = self.invoke(script, variable, setting, 0)
                    self.assertEqual(0, result.returncode, result.stderr)
                    if setting == 'true':
                        self.assertIn('-D' + property_name + '=true', arguments)
                    else:
                        self.assertFalse(any(arg.startswith('-D' + property_name + '=') for arg in arguments))
                    self.assertIn('-DskipTests', arguments)


if __name__ == '__main__':
    unittest.main()
