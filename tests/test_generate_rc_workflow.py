import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).parents[1] / "src/scripts/generate_rc_workflow.py"
spec = importlib.util.spec_from_file_location("rc_generator", SCRIPT)
rc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rc)
SHA = "a" * 40


class RcBridgeTests(unittest.TestCase):
    def test_pin_validation_prevents_mutable_or_injected_uses(self):
        for pin in (None, "", "main", "v1.0.0", "a" * 39, "a" * 41, "A" * 40, SHA + "\njobs: {}", "${{ inputs.ref }}"):
            with self.subTest(pin=pin), self.assertRaises(ValueError):
                rc.generate(pin)
        self.assertEqual("QRun-IO/qqq-orb/.github/workflows/qbit-release-rc.yml@" + SHA,
                         rc.canonical(SHA)["jobs"]["release-rc"]["uses"])

    def test_only_authorized_events_and_permissions(self):
        data = rc.canonical(SHA)
        self.assertEqual({"workflow_dispatch", "pull_request", "repository_dispatch"}, set(data["on"]))
        self.assertEqual({"types": ["closed"], "branches": ["develop"]}, data["on"]["pull_request"])
        self.assertEqual({"types": ["qbit-rc-published"]}, data["on"]["repository_dispatch"])
        self.assertEqual({"contents": "write", "actions": "read", "checks": "read"}, data["permissions"])
        job = data["jobs"]["release-rc"]
        self.assertEqual({"if", "uses", "with", "secrets"}, set(job))
        self.assertEqual("inherit", job["secrets"])
        self.assertEqual("github.event_name == 'workflow_dispatch' || github.event_name == 'repository_dispatch' || (github.event_name == 'pull_request' && github.event.pull_request.merged == true && github.event.pull_request.base.ref == 'develop' && contains(github.event.pull_request.labels.*.name, 'release:rc'))", job["if"])

    def test_manual_retry_and_callback_inputs_only_reach_worker(self):
        data = rc.canonical(SHA)
        inputs = data["on"]["workflow_dispatch"]["inputs"]
        passed = data["jobs"]["release-rc"]["with"]
        self.assertEqual({"dry_run", "finalize", "merge_sha", "bump_sha", "branch", "version"}, set(inputs))
        self.assertEqual(set(inputs), set(passed))
        for name in ("dry_run", "finalize"):
            self.assertEqual("boolean", inputs[name]["type"])
            self.assertIs(False, inputs[name]["default"])
        self.assertEqual("${{ github.event_name == 'repository_dispatch' || (github.event_name == 'workflow_dispatch' && inputs.finalize) }}", passed["finalize"])
        self.assertEqual("${{ github.event_name == 'workflow_dispatch' && inputs.dry_run || false }}", passed["dry_run"])
        for name in ("merge_sha", "bump_sha", "branch", "version"):
            self.assertEqual("string", inputs[name]["type"])
            self.assertEqual("", inputs[name]["default"])
            self.assertEqual("${{ github.event_name == 'repository_dispatch' && github.event.client_payload." + name + " || inputs." + name + " || '' }}", passed[name])

    def test_cli_canonical_check_rejects_drift_and_duplicate_keys(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "release-rc.yml"
            command = [sys.executable, str(SCRIPT), "--ref", SHA, "--check", str(path)]
            path.write_bytes(rc.generate(SHA).encode())
            self.assertEqual(0, subprocess.run(command, capture_output=True).returncode)
            for mutation in (rc.generate(SHA) + "permissions: {}\n", rc.generate(SHA).replace("contents: write", "contents: read"), rc.generate(SHA).replace(SHA, "main")):
                path.write_bytes(mutation.encode())
                self.assertNotEqual(0, subprocess.run(command, capture_output=True).returncode)


if __name__ == "__main__":
    unittest.main()
