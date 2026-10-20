import json
from pathlib import Path
import unittest
import yaml

ROOT = Path(__file__).resolve().parents[1]


def job(name):
    return yaml.safe_load((ROOT / ("src/jobs/" + name + ".yml")).read_text())


class AllAndStarterContracts(unittest.TestCase):
    def test_complete_reactor_once_then_actual_smoke_without_rebuild(self):
        verify = job("all_verify")
        commands = [s["run"]["command"] for s in verify["steps"] if isinstance(s, dict) and "run" in s]
        self.assertIn("mvn -B -ntp --update-snapshots clean verify", commands)
        self.assertEqual(sum("clean verify" in c for c in commands), 1)
        self.assertTrue(any("unittest discover" in c for c in commands))
        self.assertTrue(any("dependency:build-classpath" in c for c in commands))
        smoke = job("all_smoke")
        self.assertIn("scripts/run_core_smoke.py", str(smoke))
        self.assertIn("scripts/run_full_smoke.py", str(smoke))
        self.assertNotIn("mvn run", str(smoke))
        self.assertNotIn("clean verify", str(smoke))
        for name in ("all_smoke", "all_develop_image"):
            steps = job(name)["steps"]
            attached = next(i for i, s in enumerate(steps) if isinstance(s, dict) and "attach_workspace" in s)
            checked = next(i for i, s in enumerate(steps) if "scripts/qqq_all_artifact.sh" in str(s))
            self.assertLess(attached, checked)

    def test_all_template_runs_full_and_core_after_verification(self):
        data = json.loads((ROOT / "src/scripts/templates/all.json").read_text())
        entries = data["workflows"]["verify-and-smoke"]["jobs"]
        self.assertEqual(len(entries), 3)
        for entry in entries[1:]:
            self.assertEqual(entry["qqq-orb/all_smoke"]["requires"], ["build-and-test"])
        self.assertEqual({e["qqq-orb/all_smoke"]["profile"] for e in entries[1:]}, {"core", "full"})

    def test_starter_preserves_existing_test_only_contract(self):
        data = json.loads((ROOT / "src/scripts/templates/app-starter.json").read_text())
        entries = data["workflows"]["test_only"]["jobs"]
        self.assertEqual(len(entries), 1)
        options = entries[0]["qqq-orb/mvn_test_only"]
        self.assertEqual(options["context"], ["qqq-maven-registry-credentials"])
        self.assertEqual(options["filters"], {"tags": {"ignore": "/.*/"}})
        self.assertIs(options["compile_before_verify"], False)
        self.assertNotIn("publish", str(data))

    def test_guarded_release_remains_independent_and_cold(self):
        text = (ROOT / ".github/workflows/qqq-all-release.yml").read_text()
        data = yaml.load(text, Loader=yaml.BaseLoader)
        self.assertIn("workflow_call", data["on"])
        release = data["jobs"]["release"]
        self.assertEqual(release["environment"], "qqq-all-release")
        self.assertEqual(data["concurrency"]["cancel-in-progress"], "false")
        for proof in ('test "$RELEASE_ENABLED" = true', 'test "$LICENSE_CLEARED" = true', 'test "$RELEASE_SHA" = "$GITHUB_SHA"', '--smoke-run', '--smoke-jobs', '--tag-object', 'requireReleaseDeps', '-Dmaven.repo.local="$RUNNER_TEMP/release-m2" verify', '--public-inputs', '--verify-tag', 'ghcr-tags-final.txt'):
            self.assertIn(proof, text)
        self.assertIn('refs/heads/develop', text)


if __name__ == "__main__":
    unittest.main()
