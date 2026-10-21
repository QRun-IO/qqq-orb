"""Voyage's authoritative CI contracts, extracted from source 9f598cc105ef."""
import json
import os
import subprocess
import tempfile
from pathlib import Path
import re
import unittest

TEMPLATE = json.loads((Path(__file__).resolve().parents[1] / "src/scripts/templates/voyage.json").read_text())


def matches(pattern, branch):
    if isinstance(pattern, list):
        return any(matches(p, branch) for p in pattern)
    if pattern.startswith("/") and pattern.endswith("/"):
        return re.fullmatch(pattern[1:-1], branch) is not None
    return pattern == branch


def selected(branch):
    found = []
    for workflow, body in TEMPLATE["workflows"].items():
        for invocation in body["jobs"]:
            name, options = next(iter(invocation.items()))
            filters = options.get("filters", {}).get("branches", {})
            if "only" in filters and not matches(filters["only"], branch):
                continue
            if "ignore" in filters and matches(filters["ignore"], branch):
                continue
            found.append((workflow, name, options))
    return found


class VoyageContract(unittest.TestCase):
    def test_each_supported_branch_has_one_validation_owner(self):
        for branch, workflow in (("feature/example", "pull-request"), ("hotfix/example", "pull-request"), ("develop", "develop"), ("main", "release"), ("release/1.0", "release")):
            with self.subTest(branch=branch):
                jobs = selected(branch)
                self.assertEqual({w for w, _, _ in jobs}, {workflow})
                self.assertEqual([n for _, n, _ in jobs].count("build-and-test"), 1)
        self.assertEqual(selected("release-please--branches--main"), [])

    def test_verify_owns_tests_quality_and_coverage_without_skips(self):
        jobs = TEMPLATE["jobs"]
        self.assertNotIn("coverage", jobs)
        self.assertNotIn("code-quality", jobs)
        steps = jobs["build-and-test"]["steps"]
        commands = [s["run"]["command"] for s in steps if isinstance(s, dict) and "run" in s]
        self.assertEqual(commands, ["mvn clean verify -B -T4 --update-snapshots --no-transfer-progress"])
        full = json.dumps(jobs)
        self.assertNotIn("mvn test", full)
        self.assertNotIn("jacoco.skip", full)
        self.assertNotIn("skipTests", full)
        self.assertLess(steps.index("qqq-orb/mvn_cache_restore"), steps.index("qqq-orb/mvn_cache_save"))

    def test_unit_integration_and_coverage_evidence_retained(self):
        steps = TEMPLATE["jobs"]["build-and-test"]["steps"]
        results = [s["store_test_results"]["path"] for s in steps if isinstance(s, dict) and "store_test_results" in s]
        self.assertEqual(results, ["target/surefire-reports", "target/failsafe-reports"])
        paths = next(s["persist_to_workspace"]["paths"] for s in steps if isinstance(s, dict) and "persist_to_workspace" in s)
        for path in ("target/site", "target/jacoco.exec", "target/voyage.jar", "target/classes", "target/test-classes"):
            self.assertIn(path, paths)
        sonar = json.dumps(TEMPLATE["jobs"]["sonar-scan"])
        self.assertIn("target/site/jacoco/jacoco.xml", sonar)
        self.assertIn("attach_workspace", sonar)

    def test_all_workflow_dependencies_exist_and_preserve_release_boundaries(self):
        for workflow, body in TEMPLATE["workflows"].items():
            names = {next(iter(entry)) for entry in body["jobs"]}
            for entry in body["jobs"]:
                name, options = next(iter(entry.items()))
                self.assertIn(name, TEMPLATE["jobs"])
                self.assertTrue(set(options.get("requires", [])).issubset(names))
        for branch in ("feature/example", "release/1.0", "develop"):
            self.assertNotIn("update-cd-repo", [n for _, n, _ in selected(branch)])
            self.assertNotIn("release-please", [n for _, n, _ in selected(branch)])
        main = {n: o for _, n, o in selected("main")}
        self.assertEqual(main["update-cd-repo"]["requires"], ["docker-build"])
        self.assertEqual(main["release-please"]["requires"], ["docker-build"])
        self.assertEqual(main["docker-build"]["requires"], ["build-and-test", "secrets-scan", "sast-scan", "security-scan"])

    def test_dependency_scan_propagates_findings_and_operational_errors(self):
        command = next(s["run"]["command"] for s in TEMPLATE["jobs"]["security-scan"]["steps"]
                       if isinstance(s, dict) and "run" in s)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "bin").mkdir()
            docker = root / "bin/docker"
            docker.write_text('#!/bin/sh\nexit "$SCANNER_RESULT"\n')
            docker.chmod(0o755)
            (root / "target").mkdir()
            (root / "target/voyage.jar").write_bytes(b"artifact")
            env = {**os.environ, "HOME": directory, "PATH": str(root / "bin") + os.pathsep + os.environ["PATH"],
                   "CIRCLE_BRANCH": "develop"}
            for code in (0, 1, 2):
                result = subprocess.run(["bash", "-c", command], cwd=root,
                                        env={**env, "SCANNER_RESULT": str(code)}, capture_output=True)
                self.assertEqual(result.returncode, code)
            (root / "target/voyage.jar").unlink()
            result = subprocess.run(["bash", "-c", command], cwd=root,
                                    env={**env, "SCANNER_RESULT": "0"}, capture_output=True)
            self.assertNotEqual(result.returncode, 0)

    def test_security_policies_and_destinations_preserved(self):
        jobs = TEMPLATE["jobs"]
        self.assertIn('--exit-code 1', json.dumps(jobs["docker-build"]))
        self.assertIn('--severity CRITICAL,HIGH', json.dumps(jobs["docker-build"]))
        self.assertIn('ghcr.io/qrun-io/voyage', json.dumps(jobs["docker-build"]))
        self.assertIn('overlays/production/kustomization.yaml', json.dumps(jobs["update-cd-repo"]))
        owasp = '\n'.join(s["run"]["command"] for s in jobs["security-scan"]["steps"] if isinstance(s, dict) and "run" in s)
        self.assertIn('--severity HIGH,CRITICAL --exit-code 1', owasp)
        self.assertIn('target/voyage.jar:/scan/voyage.jar:ro', owasp)
        self.assertIn('aquasec/trivy:0.76.0@sha256:', owasp)
        self.assertNotIn('--ignore-unfixed', owasp)
        self.assertNotIn('NVD_API_KEY', owasp)
        self.assertNotIn('mvn ', owasp)
        self.assertIn('set -euo pipefail', owasp)
        self.assertEqual(jobs["security-scan"]["resource_class"], "medium")
        for workflow in TEMPLATE["workflows"].values():
            for invocation in workflow["jobs"]:
                if "security-scan" in invocation:
                    self.assertNotIn("context", invocation["security-scan"])
        self.assertIn('./gitleaks detect', json.dumps(jobs["secrets-scan"]))
        self.assertIn('|| true', json.dumps(jobs["sast-scan"]))
        self.assertIn('makeAggregateBom', json.dumps(jobs["sbom"]))


if __name__ == "__main__":
    unittest.main()
