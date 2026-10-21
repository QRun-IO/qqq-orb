"""Protect existing Android gates and execute the centralized policy validator."""
import contextlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import tempfile
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
        for name in ("unit-test", "android-test"):
            self.assertEqual(after["jobs"][name], before["jobs"][name])
        self.assertEqual(after["jobs"]["maven-deploy"]["executor"], before["jobs"]["maven-deploy"]["executor"])
        self.assertEqual(after["jobs"]["maven-deploy"]["steps"][:2], before["jobs"]["maven-deploy"]["steps"][:2])
        entries = after["workflows"]["test-and-build"]["jobs"]
        self.assertEqual(entries[0], "unit-test")
        self.assertEqual(entries[1], {"android-test": {}})
        publish = entries[2]["maven-deploy"]
        self.assertEqual(publish["context"], ["qqq-maven-registry-credentials"])
        self.assertEqual(publish["requires"], ["unit-test", "android-test"])
        self.assertEqual(publish["filters"], {"branches": {"only": "main"}})
        # No new dormant Firebase benchmark or nonexistent app module build.
        self.assertNotIn("benchmarks-ftl", after["jobs"])

    def test_android_publication_uses_shared_credentials_without_persisting_them(self):
        data = json.loads((ROOT / "src/scripts/templates/android.json").read_text())
        steps = data["jobs"]["maven-deploy"]["steps"]
        self.assertEqual(len(steps), 3)
        command = steps[2]["run"]["command"]
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            runner = root / "gradlew"
            runner.write_text('''#!/bin/bash
set -eu
test "$1" = --console=plain
test "$2" = publishMavenPublicationToGithubQqqMavenRegistryRepository
test "$ORG_GRADLE_PROJECT_githubQqqMavenRegistryUsername" = fixture-user
test "$ORG_GRADLE_PROJECT_githubQqqMavenRegistryPassword" = fixture-password
touch invoked
''')
            runner.chmod(0o755)
            python = root / "python3"
            python.write_text("#!/bin/bash\ncat >/dev/null\n[[ ${DENY_ACCESS:-0} == 0 ]] || exit 1\necho fixture-user\n")
            python.chmod(0o755)
            base = {**os.environ, "GITHUB_TOKEN": "fixture-password",
                    "PATH": str(root) + os.pathsep + os.environ["PATH"]}
            for mode in ("missing", "denied", "success"):
                env = dict(base)
                if mode == "missing":
                    env.pop("GITHUB_TOKEN")
                elif mode == "denied":
                    env["DENY_ACCESS"] = "1"
                result = subprocess.run(["bash", "-c", command], cwd=root, env=env, capture_output=True, text=True)
                self.assertEqual(result.returncode == 0, mode == "success")
                self.assertEqual((root / "invoked").exists(), mode == "success")
                self.assertFalse((root / "gradle.properties").exists())
                self.assertNotIn("fixture-password", result.stdout + result.stderr)

    def test_android_registry_preflight_fails_closed(self):
        data = json.loads((ROOT / "src/scripts/templates/android.json").read_text())
        command = data["jobs"]["maven-deploy"]["steps"][2]["run"]["command"]
        script = command.split("<<'PYTHON'\n", 1)[1].split("\nPYTHON", 1)[0]
        for identity, permissions, allowed in (({"login": "fixture-user"}, {"push": True}, True),
                                             ({"login": "fixture-user"}, {"push": False}, False),
                                             ({}, {"push": True}, False)):
            opener = mock.Mock()
            responses = [json.dumps(identity), json.dumps({"permissions": permissions})]
            opener.open.side_effect = lambda *args, **kwargs: io.StringIO(responses.pop(0))
            with mock.patch("urllib.request.build_opener", return_value=opener), \
                    mock.patch.dict(os.environ, {"GITHUB_TOKEN": "fixture-password"}), \
                    contextlib.redirect_stdout(io.StringIO()) as output:
                if allowed:
                    exec(compile(script, "registry-preflight", "exec"), {})
                    self.assertEqual(output.getvalue().strip(), "fixture-user")
                else:
                    with self.assertRaises(SystemExit):
                        exec(compile(script, "registry-preflight", "exec"), {})
                self.assertNotIn("fixture-password", output.getvalue())

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
