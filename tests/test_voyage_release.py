"""Execute Voyage release commands; CD implementation belongs to Munitor."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = json.loads((ROOT / "src/scripts/templates/voyage.json").read_text())
COMMAND = next(step["run"]["command"] for step in TEMPLATE["jobs"]["release-please"]["steps"]
               if isinstance(step, dict) and "run" in step)


class VoyageRelease(unittest.TestCase):
    def run_release(self, fail=False):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            npx = root / "npx"
            npx.write_text('''#!/usr/bin/env python3
import json, os, sys
with open(os.environ['EVENTS'], 'a') as output:
    output.write(json.dumps(sys.argv[1:])+'\\n')
assert '--target-branch=main' in sys.argv
if os.environ['FAILURE']=='true' and 'github-release' in sys.argv: sys.exit(25)
''')
            npx.chmod(0o755)
            events = root / "events.jsonl"
            env = {**os.environ, "PATH": str(root) + os.pathsep + os.environ["PATH"],
                   "EVENTS": str(events), "FAILURE": str(fail).lower(), "GITHUB_TOKEN": "fixture-token"}
            result = subprocess.run(["bash", "-c", COMMAND], cwd=root, env=env, capture_output=True, text=True)
            return result, [json.loads(line) for line in events.read_text().splitlines()]

    def test_release_targets_main_for_both_commands(self):
        result, rows = self.run_release()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([args[1] for args in rows], ['github-release', 'release-pr'])

    def test_release_failure_is_not_hidden_by_second_command(self):
        result, rows = self.run_release(fail=True)
        self.assertEqual(result.returncode, 25, result.stderr)
        self.assertEqual(len(rows), 1)
