#!/usr/bin/env python3
"""Protect native Next coverage while moving worker ownership into the orb."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest

import yaml

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("next_bridge", ROOT / "src/scripts/generate_next_workflow.py")
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)


class NextNativeTests(unittest.TestCase):
    def test_circle_keeps_tag_validation_and_removes_branch_checks(self):
        before = yaml.safe_load((ROOT / "tests/fixtures/next-circle.yml").read_text(encoding="utf-8"))
        after = json.loads((ROOT / "src/scripts/templates/frontend-next.json").read_text(encoding="utf-8"))
        self.assertEqual(set(after["workflows"]), {"publish_release"})
        expected_steps = before["jobs"]["publish_dashboard_jar"]["steps"][1:]
        self.assertEqual(after["jobs"]["publish_dashboard_jar"]["steps"], expected_steps)
        self.assertNotIn("commands", after)
        original_jobs = before["workflows"]["publish_release"]["jobs"]
        jobs = after["workflows"]["publish_release"]["jobs"]
        self.assertEqual(jobs[1], original_jobs[1])
        self.assertEqual(jobs[0]["qqq-orb/node_app_build"]["filters"]["tags"],
                         original_jobs[0]["qqq-orb/node_app_build"]["filters"]["tags"])
        for job in jobs:
            self.assertEqual(next(iter(job.values()))["filters"]["branches"], {"ignore": "/.*/"})
        spec = importlib.util.spec_from_file_location("standard", ROOT / "src/scripts/validate_standard.py")
        standard = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(standard)
        caller = standard.canonical_caller("frontend-next", "0.7.0")
        options = caller["workflows"]["setup"]["jobs"][0]["qqq-orb/generate_pipeline"]
        self.assertEqual(options["filters"]["branches"], {"ignore": "/.*/"})

    def test_workers_keep_every_existing_job_and_step(self):
        for source, worker in (("ci.yml", "next-ci.yml"), ("acceptance.yml", "next-acceptance.yml"),
                               ("dashboard-image.yml", "next-dashboard-image.yml")):
            before = yaml.safe_load((ROOT / "tests/fixtures" / ("next-" + source)).read_text(encoding="utf-8"))
            after = yaml.safe_load((ROOT / ".github/workflows" / worker).read_text(encoding="utf-8"))
            # The package-fetch policy adds bounded setup only; retain exact test gates.
            for job in after["jobs"].values():
                for step in job.get("steps", []):
                    if step.get("name") == "Install browser system dependencies":
                        self.assertEqual(step["timeout-minutes"], 10)
                        command = step["run"].strip().splitlines()[-1]
                        self.assertTrue(command.startswith("pnpm exec playwright install-deps "))
                        step.clear()
                        step["run"] = command
            self.assertEqual(before["jobs"], after["jobs"], worker)
            self.assertEqual(before.get("env"), after.get("env"), worker)
            self.assertEqual(before.get("permissions"), after.get("permissions"), worker)
            self.assertIn("workflow_call", after[True])  # PyYAML's YAML1.1 interpretation of 'on'.
            self.assertNotIn("push", after[True])
            self.assertNotIn("pull_request", after[True])

    def test_acceptance_selector_retains_18_full_and_4_pr_cells(self):
        path = (ROOT / "tests/fixtures/next-acceptance-select.mjs").as_uri()
        code = f"import {{planAcceptance}} from {json.dumps(path)}; console.log(JSON.stringify([planAcceptance({{eventName:'push'}}),planAcceptance({{eventName:'pull_request',paths:['src/components/navigation.tsx']}}),planAcceptance({{eventName:'pull_request',labels:['full-acceptance']}})]))"
        full, pr, labelled = json.loads(subprocess.check_output(["node", "--input-type=module", "-e", code], text=True))
        self.assertEqual(len(full["matrix"]["include"]), 18)
        self.assertEqual(len(pr["matrix"]["include"]), 4)
        self.assertEqual(labelled, full)
        self.assertEqual({x["project"] for x in full["matrix"]["include"]}, {"chromium", "firefox", "webkit", "mobile", "tablet"})
        self.assertEqual({x["project"] for x in pr["matrix"]["include"]}, {"chromium", "mobile"})

    def test_bridge_pins_workers_and_limits_label_reruns(self):
        ref = "a" * 40
        caller = bridge.canonical_next(ref)
        self.assertEqual(set(caller["jobs"]), {"ci", "acceptance", "dashboard-image"})
        for job in caller["jobs"].values():
            self.assertTrue(job["uses"].startswith("QRun-IO/qqq-orb/.github/workflows/next-"))
            self.assertTrue(job["uses"].endswith("@" + ref))
        self.assertIn("github.event.label.name == 'full-acceptance'", caller["jobs"]["acceptance"]["if"])
        for name in ("ci", "dashboard-image"):
            self.assertIn("!contains", caller["jobs"][name]["if"])
            self.assertNotIn("full-acceptance", caller["jobs"][name]["if"])
        self.assertEqual(caller["jobs"]["dashboard-image"]["permissions"], {"contents": "read", "packages": "write"})
        self.assertEqual(yaml.safe_load(yaml.safe_dump(caller)), caller)
        for invalid in ("main", "v1.0.0", "", "a" * 39, "not-a-ref"):
            with self.assertRaises(ValueError):
                bridge.canonical_next(invalid)


if __name__ == "__main__":
    unittest.main()
