"""Run the workflow's publication shell with a recording CLI, never GitHub."""

import json
import os
import subprocess
import tempfile
import yaml
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def workflow_shell(name):
    worker = yaml.safe_load((ROOT / ".github/workflows/qqq-all-release.yml").read_text())
    return next(step["run"] for step in worker["jobs"]["release"]["steps"]
                if step.get("name") == name)


class ReleaseWorkflowTest(unittest.TestCase):
    def test_rc_is_prerelease_never_latest_and_ga_keeps_existing_release_behavior(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            gh = root / "gh"
            gh.write_text("#!/usr/bin/env python3\nimport json, os, sys\n"
                          "with open(os.environ['CALLS'], 'w') as f: json.dump(sys.argv[1:], f)\n")
            gh.chmod(0o755)
            calls = root / "calls.json"
            for version in ("4.1.0", "4.1.0-RC.1", "4.1.0-RC.2"):
                calls.unlink(missing_ok=True)
                environment = {**os.environ, "PATH": directory + os.pathsep + os.environ["PATH"],
                               "CALLS": str(calls), "VERSION": version, "TAG": version,
                               "RUNNER_TEMP": directory, "GITHUB_REPOSITORY": "QRun-IO/qqq-all"}
                result = subprocess.run(["bash", "-c", workflow_shell("Publish GitHub release with Compose bundle")],
                                        env=environment, capture_output=True, text=True)
                if version == "4.1.0-RC.2":
                    self.assertNotEqual(0, result.returncode)
                    self.assertFalse(calls.exists())
                    continue
                self.assertEqual(0, result.returncode, result.stderr)
                args = json.loads(calls.read_text())
                self.assertEqual(["release", "create", version], args[:3])
                self.assertIn(str(root / ("qqq-all-" + version + ".tar.gz")), args)
                self.assertIn("--verify-tag", args)
                if version == "4.1.0-RC.1":
                    self.assertIn("--prerelease", args)
                    self.assertIn("--latest=false", args)
                else:
                    self.assertNotIn("--prerelease", args)
                    self.assertNotIn("--latest=false", args)
