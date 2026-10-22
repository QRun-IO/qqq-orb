#!/usr/bin/env python3
"""Run the generated link-check shell with controlled server/readiness commands."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

class MarketingLinkCheckTests(unittest.TestCase):
    def run_check(self, ready, link_status):
        template = json.loads((ROOT / 'src/scripts/templates/marketing.json').read_text())
        build = template['workflows']['pr-checks']['jobs'][0]['munitor/node_build_and_test']
        command = json.loads(build['test_commands'])[5]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            scripts = {
                'npm': '#!/bin/bash\nif [ "$2" = start ]; then echo $$ > "$TEST_ROOT/server.pid"; exec /bin/sleep 30; fi\necho checked > "$TEST_ROOT/checked"\nexit "$LINK_STATUS"\n',
                'curl': '#!/bin/bash\nexit "$READY_STATUS"\n',
                'sleep': '#!/bin/bash\n/bin/sleep 0.01\n',
            }
            for name, text in scripts.items():
                file = root / name
                file.write_text(text)
                file.chmod(0o755)
            env = {**os.environ, 'PATH': str(root) + ':' + os.environ['PATH'],
                   'TEST_ROOT': str(root), 'READY_STATUS': str(ready), 'LINK_STATUS': str(link_status)}
            result = subprocess.run(['bash', '-c', command], env=env, capture_output=True, timeout=10)
            self.assertEqual((root / 'checked').exists(), ready == 0)
            pid_file = root / 'server.pid'
            if pid_file.exists():
                with self.assertRaises(ProcessLookupError):
                    os.kill(int(pid_file.read_text()), 0)
            return result

    def test_worker_input_is_generated_before_tests(self):
        import yaml
        template = json.loads((ROOT / 'src/scripts/templates/marketing.json').read_text())
        for workflow in template['workflows'].values():
            build = workflow['jobs'][0]['munitor/node_build_and_test']
            command = json.loads(build['test_commands'])[0]
            with tempfile.TemporaryDirectory() as directory:
                subprocess.run(['bash', '-c', command], cwd=directory, check=True)
                actual = yaml.safe_load((Path(directory) / '.munitor.yml').read_text())
                self.assertEqual(actual, {'pipeline': 'node-webapp', 'node_version': 22,
                                          'docker': {'use_repo_dockerfile': True}})

    def test_ready_server_runs_links_and_is_cleaned_up(self):
        self.assertEqual(self.run_check(0, 0).returncode, 0)

    def test_broken_links_fail_and_server_is_cleaned_up(self):
        self.assertEqual(self.run_check(0, 7).returncode, 7)

    def test_unready_server_fails_without_running_links(self):
        result = self.run_check(1, 0)
        self.assertEqual(result.returncode, 1)
        self.assertIn(b'did not become ready', result.stderr)

if __name__ == '__main__':
    unittest.main()
