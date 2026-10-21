"""Protect existing Android gates and execute the centralized policy validator."""
import contextlib
import io
import json
from pathlib import Path, PurePosixPath
import unittest
from unittest import mock

import yaml

ROOT = Path(__file__).resolve().parents[1]


class MobilePolicyTests(unittest.TestCase):
    def test_android_preserves_executed_jobs_and_repairs_main_dependencies(self):
        before = yaml.safe_load((ROOT / "tests/fixtures/android-circle.yml").read_text())
        after = json.loads((ROOT / "src/scripts/templates/android.json").read_text())
        self.assertEqual(after["orbs"], before["orbs"])
        self.assertEqual(set(after["jobs"]), {"unit-test", "android-test", "maven-deploy"})
        for name, job in after["jobs"].items():
            self.assertEqual(job, before["jobs"][name])
        entries = after["workflows"]["test-and-build"]["jobs"]
        self.assertEqual(entries[0], "unit-test")
        self.assertEqual(entries[1], {"android-test": {}})
        publish = entries[2]["maven-deploy"]
        self.assertEqual(publish["requires"], ["unit-test", "android-test"])
        self.assertEqual(publish["filters"], {"branches": {"only": "main"}})
        # No new dormant Firebase benchmark or nonexistent app module build.
        self.assertNotIn("benchmarks-ftl", after["jobs"])

    def test_policy_stays_small_and_validates_actual_pattern_content(self):
        data = json.loads((ROOT / "src/scripts/templates/mcp-policy.json").read_text())
        job = data["jobs"]["validate-patterns"]
        self.assertEqual(job["resource_class"], "small")
        self.assertIn("PyYAML==6.0.3", job["steps"][1]["run"]["command"])
        command = job["steps"][2]["run"]["command"]
        self.assertTrue(command.startswith("python3 \\<< 'EOF'\n"), "CircleCI requires escaped heredoc interpolation markers")
        script = command.split("\n", 1)[1].rsplit("\nEOF", 1)[0]
        valid = "id: example\ntitle: Example\ncategory: test\ndescription: test\ncontent: test\n"
        for text, expected in ((valid, 0), ("id: incomplete\n", 1), ("[invalid", 1)):
            with self.subTest(text=text), mock.patch.object(Path, "rglob", return_value=[PurePosixPath("patterns/example.yaml")]), \
                    mock.patch("builtins.open", return_value=io.StringIO(text)), \
                    contextlib.redirect_stdout(io.StringIO()):
                if expected:
                    with self.assertRaises(SystemExit) as raised:
                        exec(compile(script, "policy-validator", "exec"), {})
                    self.assertEqual(raised.exception.code, expected)
                else:
                    exec(compile(script, "policy-validator", "exec"), {})


if __name__ == "__main__":
    unittest.main()
