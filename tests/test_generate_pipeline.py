#!/usr/bin/env python3
"""Offline regression of actual source and packed CircleCI generator commands."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import yaml

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src/scripts/generate_pipeline.py"
PACKED = None
if "--packed" in sys.argv:
    index = sys.argv.index("--packed")
    PACKED = Path(sys.argv[index + 1])
    del sys.argv[index:index + 2]
spec = importlib.util.spec_from_file_location("pipeline", SOURCE)
pipeline = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pipeline)
MANIFEST = {"profile": "qbit", "orb_version": "0.7.0", "default_branch": "develop"}


class MarketingContractTests(unittest.TestCase):
    def test_munitor_render_with_explicit_build_and_single_continuation(self):
        baseline = yaml.safe_load((ROOT / "tests/fixtures/marketing-munitor-0311-rendered.yml").read_text(encoding="utf-8"))
        # The original delegated job never builds: require the shared profile
        # to prepare the standalone artifact before browser/Lighthouse checks.
        for workflow in baseline["workflows"].values():
            for entry in workflow["jobs"]:
                if "munitor/node_build_and_test" in entry:
                    build = entry["munitor/node_build_and_test"]
                    build["test_commands"] = json.dumps([
                        "npm run lint", "npm run build",
                        *json.loads(build["test_commands"])])
        for branch in ("feature/example", "main", "develop", "staging", "release/1"):
            result = pipeline.marketing_template({}, branch, "")
            self.assertEqual(result, baseline)
            self.assertNotIn("setup", result)
            self.assertEqual(result["orbs"], {"munitor": "kof22/munitor@0.3.11"})
            self.assertEqual(sum(len(w["jobs"]) for w in result["workflows"].values()), 33)
            self.assertNotIn("generate_pipeline", json.dumps(result))

    def test_production_deployment_and_actual_test_contracts(self):
        result = pipeline.marketing_template({}, "main", "")
        for name, workflow in result["workflows"].items():
            jobs = {next(iter(entry)): next(iter(entry.values())) for entry in workflow["jobs"]}
            build = jobs["munitor/node_build_and_test"]
            self.assertEqual(build["node_version"], "22")
            self.assertEqual(json.loads(build["test_commands"]), [
                "npm run lint", "npm run build",
                "npx playwright install chromium --with-deps",
                "npm run test:chromium", "npm run lighthouse"])
            if name == "production":
                cd = jobs["munitor/update_cd_repo"]
                self.assertEqual(cd["cd_repo"], "KofTwentyTwo/cluster-gitops")
                self.assertEqual(cd["cd_path"], "tenants/qrun/website/kustomization.yaml")
                self.assertEqual(cd["filters"], {"branches": {"only": "main"}})
                self.assertEqual(cd["requires"], ["docker-build-push"])
                self.assertEqual(jobs["munitor/github_release"]["requires"], ["docker-build-push"])
                self.assertEqual(jobs["munitor/docker_build_push"]["health_path"], "/")
                self.assertEqual(jobs["munitor/docker_build_push"]["health_port"], "3000")
            else:
                self.assertNotIn("munitor/update_cd_repo", jobs)
        result["workflows"].clear()
        self.assertEqual(len(pipeline.marketing_template({}, "main", "")["workflows"]), 5)

    def test_marketing_manifest_rejects_custom_policy_and_wrong_branch(self):
        data = {"profile": "marketing", "orb_version": "0.7.0", "default_branch": "main"}
        with mock.patch.object(Path, "read_text", return_value=yaml.safe_dump(data)):
            self.assertEqual(pipeline.load_manifest("unused", "0.7.0")["profile"], "marketing")
        for change in ({"default_branch": "develop"}, {"docs_only": True},
                       {"publish": {"release": False}}, {"node_version": "24"}):
            with mock.patch.object(Path, "read_text", return_value=yaml.safe_dump({**data, **change})):
                with self.assertRaises(pipeline.ManifestError):
                    pipeline.load_manifest("unused", "0.7.0")


class RuntimeBooleanTests(unittest.TestCase):
    def test_qbit_main_and_tag_release_policy_preserves_provenance(self):
        base = {"profile": "qbit", "orb_version": "0.7.0", "default_branch": "develop"}
        for policy, tag, expected in (("stable", "v1.2.3", "publish_release"),
                                      ("stable", "v1.2.3-RC.1", "test_only"),
                                      ("v-prefix", "v1.2.3-RC.1", "publish_release"),
                                      ("v-prefix", "vanything", "publish_release"),
                                      ("none", "v1.2.3", "test_only")):
            with mock.patch.object(Path, "read_text", return_value=yaml.safe_dump({**base, "release_tag_policy": policy})):
                config = pipeline.load_manifest("unused", "0.7.0")
            with mock.patch.object(pipeline, "git", return_value=b"verified-head\n"):
                self.assertEqual(list(pipeline.qbit_template(config, "", tag)["workflows"]), [expected])
            with mock.patch.object(pipeline, "git", return_value=None):
                self.assertEqual(list(pipeline.qbit_template(config, "", tag)["workflows"]), ["test_only"])
        with mock.patch.object(Path, "read_text", return_value=yaml.safe_dump({**base, "release_on_main": True})):
            config = pipeline.load_manifest("unused", "0.7.0")
        self.assertIn("publish_release", pipeline.qbit_template(config, "main", "")["workflows"])
        config["publish"]["release"] = False
        self.assertIn("test_only", pipeline.qbit_template(config, "main", "")["workflows"])

    def test_qbit_test_exclusions_are_central_fixed_patterns(self):
        config = {"orb_version": "0.7.0", "publish": {}, "docs_only": False,
                  "java_version": "21", "browsers": True, "api_checks": False,
                  "test_branch_policy": "feature"}
        result = pipeline.qbit_template(config, "integration-example", "")
        options = result["workflows"]["test_only"]["jobs"][0]["qqq-orb/mvn_test_only"]
        self.assertEqual(options["filters"]["branches"]["ignore"],
                         ["automation/qbit-rc-pending", "/(develop|main|release/.*|integration.*)/"])

    def test_all_publication_is_explicit_and_develop_only(self):
        config = {"orb_version": "0.7.0", "publish": {"snapshot": False}, "publish_context": "verified"}
        for branch in ("develop", "main", "feature/example"):
            result = pipeline.all_template(config, branch, "")
            self.assertEqual(len(result["workflows"]["verify-and-smoke"]["jobs"]), 3)
        config["publish"]["snapshot"] = True
        result = pipeline.all_template(config, "develop", "")
        image = result["workflows"]["verify-and-smoke"]["jobs"][-1]["qqq-orb/all_develop_image"]
        self.assertEqual(image["requires"], ["build-and-test", "core", "full"])
        self.assertEqual(image["context"], ["verified"])
        for branch, tag in (("main", ""), ("develop", "v1.0.0")):
            self.assertEqual(len(pipeline.all_template(config, branch, tag)["workflows"]["verify-and-smoke"]["jobs"]), 3)

    def test_known_transport_forms_and_reject_unknown(self):
        for name in ("QQQ_CI_RUN_PLAYWRIGHT", "QQQ_CI_MONGO_DIAGNOSTICS"):
            for value in ("true", "True", "TRUE", "1", "false", "False", "FALSE", "0"):
                with mock.patch.dict(os.environ, {name: value}):
                    self.assertEqual(pipeline.runtime_boolean(name), value.lower() in ("true", "1"))
            for value in ("", "yes", "no", "unexpected", " true "):
                with mock.patch.dict(os.environ, {name: value}):
                    with self.assertRaises(pipeline.ManifestError):
                        pipeline.runtime_boolean(name)


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.env = {**os.environ, "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
                    "GIT_AUTHOR_NAME": "Fixture", "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
                    "GIT_COMMITTER_NAME": "Fixture", "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
                    "CIRCLE_SHA1": "", "CIRCLE_BRANCH": "feature/test", "CIRCLE_TAG": "",
                    "QQQ_CI_ORB_VERSION": "0.7.0", "QQQ_CI_CONTINUE": "false",
                    "QQQ_CI_OUTPUT": str(self.root / "output.json"), "QQQ_CI_MANIFEST": ".qqq-ci.yml"}
        self.git("init", "-q", "-b", "develop")
        self.write_manifest()
        (self.repo / "README.md").write_text("original\n", encoding="utf-8")
        (self.repo / "App.java").write_text("original\n", encoding="utf-8")
        self.commit()
        self.origin = self.root / "origin.git"
        self.git("clone", "-q", "--bare", str(self.repo), str(self.origin))
        self.git("remote", "add", "origin", str(self.origin))
        self.git("switch", "-q", "-c", "feature/test")

    def git(self, *args):
        return subprocess.check_output(["git", *args], cwd=self.repo, env=self.env, stderr=subprocess.DEVNULL).decode().strip()

    def commit(self):
        self.git("add", ".")
        self.git("-c", "commit.gpgsign=false", "commit", "-qm", "fixture")

    def write_manifest(self, **overrides):
        data = copy.deepcopy(MANIFEST)
        data.update(overrides)
        (self.repo / ".qqq-ci.yml").write_text(yaml.safe_dump(data), encoding="utf-8")

    def change_docs(self):
        (self.repo / "README.md").write_text("changed\n", encoding="utf-8")
        self.commit()

    def render(self, packed=False, ok=True, **environment):
        command = [sys.executable, str(SOURCE)]
        if packed:
            data = yaml.safe_load(PACKED.read_text(encoding="utf-8"))
            steps = data["commands"]["generate_pipeline"]["steps"]
            run = next(step["run"] for step in steps if step.get("run", {}).get("shell") == "python3")
            # Hosted CircleCI invokes the custom Python shell with the command as argv.
            self.assertLessEqual(len(run["command"].encode("utf-8")), 100_000)
            command = [sys.executable, "-c", run["command"]]
        result = subprocess.run(command, cwd=self.repo, env={**self.env, **environment}, capture_output=True, text=True)
        self.assertEqual(result.returncode == 0, ok, result.stderr)
        if ok:
            return json.loads((self.root / "output.json").read_text(encoding="utf-8"))
        self.assertNotIn("Traceback", result.stderr)
        return result

    def assert_full(self, result, workflow="test_only"):
        self.assertEqual(list(result["workflows"]), [workflow])
        self.assertNotIn("docs_only", result.get("jobs", {}))
        job, options = next(iter(result["workflows"][workflow]["jobs"][0].items()))
        self.assertEqual(job, "qqq-orb/mvn_test_only" if workflow == "test_only" else "qqq-orb/mvn_publish")
        self.assertEqual(options["context"], ["qqq-maven-registry-credentials"])
        self.assertFalse(options["compile_before_verify"])
        return options

    def test_defaults_and_options(self):
        options = self.assert_full(self.render())
        self.assertTrue(options["install_browsers"])
        self.assertEqual(options["java_version"], "21")
        self.write_manifest(java_version="17", browsers=False, api_checks=True)
        options = self.assert_full(self.render())
        self.assertFalse(options["install_browsers"])
        self.assertTrue(options["check_middleware_api_versions"])
        self.assertEqual(options["java_version"], "17")

    def test_branch_matrix(self):
        for branch, workflow in [("develop", "publish_snapshot"), ("release/1.0", "publish_release_candidate"),
                                 ("main", "test_only"), ("hotfix/fix", "test_only"),
                                 ("integration", "test_only"), ("", "test_only")]:
            with self.subTest(branch=branch):
                self.assert_full(self.render(CIRCLE_BRANCH=branch), workflow)

    def test_publication_toggles(self):
        self.write_manifest(publish={"snapshot": False, "release_candidate": False, "release": False})
        self.git("tag", "v1.0.0")
        for branch, tag in [("develop", ""), ("release/1.0", ""), ("", "v1.0.0")]:
            self.assert_full(self.render(CIRCLE_BRANCH=branch, CIRCLE_TAG=tag))
        self.write_manifest(publish={"asciidoc": True})
        self.assertTrue(self.assert_full(self.render(CIRCLE_BRANCH="develop"), "publish_snapshot")["publish_asciidoc"])

    def test_qbit_rc_completion_is_explicit_and_rc_only(self):
        options = self.assert_full(self.render(CIRCLE_BRANCH="release/1"), "publish_release_candidate")
        self.assertFalse(options["notify_rc_published"])
        self.write_manifest(release_completion=True)
        options = self.assert_full(self.render(CIRCLE_BRANCH="release/1"), "publish_release_candidate")
        self.assertTrue(options["notify_rc_published"])
        self.assertNotIn("notify_rc_published", self.assert_full(self.render(CIRCLE_BRANCH="develop"), "publish_snapshot"))
        self.git("tag", "v1.0.0")
        self.assertNotIn("notify_rc_published", self.assert_full(self.render(CIRCLE_TAG="v1.0.0"), "publish_release"))
        self.write_manifest(release_completion="true")
        self.render(ok=False)
        self.write_manifest(profile="core", release_completion=True)
        self.render(ok=False)

    def test_tag_provenance_and_filters(self):
        self.git("tag", "v1.0.0")
        result = self.render(CIRCLE_TAG="v1.0.0")
        options = self.assert_full(result, "publish_release")
        self.assertEqual(options["branch_type"], "release")
        self.assertEqual(options["filters"], {"branches": {"ignore": "/.*/"}, "tags": {"only": "/.*/"}})
        self.change_docs()
        self.assert_full(self.render(CIRCLE_TAG="v1.0.0"))
        self.assert_full(self.render(CIRCLE_TAG="v1.0.0-RC.1"))
        self.assert_full(self.render(CIRCLE_TAG="v9.9.9"))

    def test_checkout_provenance(self):
        self.assert_full(self.render(CIRCLE_SHA1=self.git("rev-parse", "HEAD")))
        self.render(ok=False, CIRCLE_SHA1="0" * 40)

    def test_continuation_http_success_and_safe_failure(self):
        env = {**self.env, "QQQ_CI_MANIFEST": str(self.repo / ".qqq-ci.yml"),
               "QQQ_CI_CONTINUE": "true", "CIRCLE_CONTINUATION_KEY": "fixture-key-not-real"}
        response = mock.MagicMock()
        response.__enter__.return_value.status = 200
        with mock.patch.dict(os.environ, env, clear=True), mock.patch.object(pipeline.urllib.request, "urlopen", return_value=response) as send:
            pipeline.main()
            request = send.call_args.args[0]
            payload = json.loads(request.data)
            self.assertEqual(payload["continuation-key"], "fixture-key-not-real")
            self.assertNotIn("parameters", payload)
            self.assertEqual(request.full_url, "https://circleci.com/api/v2/pipeline/continue")
        error = pipeline.urllib.error.HTTPError("https://circleci.com/api/v2/pipeline/continue", 400, "DO-NOT-PRINT-BODY", {}, None)
        with mock.patch.dict(os.environ, env, clear=True), mock.patch.object(pipeline.urllib.request, "urlopen", side_effect=error):
            with self.assertRaisesRegex(pipeline.ManifestError, r"^CircleCI continuation failed \(HTTP 400\)$"):
                pipeline.main()

    def test_release_lock_branch_is_filtered(self):
        options = self.assert_full(self.render(CIRCLE_BRANCH="automation/qbit-rc-pending"))
        self.assertEqual(options["filters"]["branches"]["ignore"], "automation/qbit-rc-pending")

    def test_strict_manifest(self):
        cases = [{"profile": "other"}, {"java_version": 21}, {"orb_version": "latest"},
                 {"orb_version": "0.6.9"}, {"browsers": "false"}, {"api_checks": 1},
                 {"docs_only": "yes"}, {"publish": {"release": "false"}},
                 {"publish": {"custom": True}}, {"jobs": {}}, {"default_branch": "anything"}]
        for case in cases:
            with self.subTest(case=case):
                self.write_manifest(**case)
                self.render(ok=False)
        for raw in ["[]", "profile: qbit\nprofile: qbit\n", "!!python/object:danger {}", "null", "[broken"]:
            (self.repo / ".qqq-ci.yml").write_text(raw, encoding="utf-8")
            self.render(ok=False)

    def enable_docs(self):
        self.write_manifest(docs_only=True)
        self.commit()
        self.git("push", "-q", "origin", "HEAD:develop")

    def test_docs_whole_branch_and_packed(self):
        self.enable_docs()
        self.change_docs()
        for packed in ([False, True] if PACKED else [False]):
            result = self.render(packed=packed)
            self.assertEqual(list(result["workflows"]), ["test_only"])
            options = result["workflows"]["test_only"]["jobs"][0]["docs_only"]
            self.assertEqual(options["name"], "qqq-orb/mvn_test_only")
            self.assertIn("git diff --check", result["jobs"]["docs_only"]["steps"][1]["run"]["command"])
        (self.repo / "App.java").write_text("changed\n", encoding="utf-8")
        self.commit()
        (self.repo / "README.md").write_text("latest documentation\n", encoding="utf-8")
        self.commit()
        self.assert_full(self.render())

    def test_docs_optout_and_release_always_full(self):
        self.change_docs()
        self.assert_full(self.render())
        self.enable_docs()
        (self.repo / "README.md").write_text("more docs\n", encoding="utf-8")
        self.commit()
        for branch, workflow in [("develop", "publish_snapshot"), ("release/1", "publish_release_candidate"), ("unknown", "test_only")]:
            self.assert_full(self.render(CIRCLE_BRANCH=branch), workflow)
        self.git("tag", "v2.0.0")
        self.assert_full(self.render(CIRCLE_TAG="v2.0.0"), "publish_release")

    def test_empty_missing_base_and_rename_code(self):
        self.enable_docs()
        self.assert_full(self.render())
        self.git("mv", "App.java", "CONTRIBUTING.md")
        self.commit()
        self.assert_full(self.render())
        self.git("remote", "remove", "origin")
        self.assert_full(self.render())

    def test_deleted_code(self):
        self.enable_docs()
        (self.repo / "App.java").unlink()
        self.commit()
        self.assert_full(self.render())

    def test_main_first_parent_and_nested_docs(self):
        self.enable_docs()
        (self.repo / "docs/nested").mkdir(parents=True)
        (self.repo / "docs/nested/a space.md").write_text("docs\n", encoding="utf-8")
        self.commit()
        self.assertIn("docs_only", self.render(CIRCLE_BRANCH="main")["jobs"])
        self.assertIn("docs_only", self.render()["jobs"])

    def test_main_default_branch(self):
        self.write_manifest(default_branch="main", docs_only=True)
        self.commit()
        self.git("push", "-q", "origin", "HEAD:main")
        self.change_docs()
        self.assertIn("docs_only", self.render()["jobs"])

    def test_core_workflow_graphs_match_baseline(self):
        self.write_manifest(profile="core")
        baseline = yaml.safe_load((ROOT / "tests/fixtures/core_pipeline_baseline.yml").read_text(encoding="utf-8"))
        self.git("tag", "v1.0.0")
        self.git("tag", "publish-fixture")
        events = [("feature/test", "", "test_only"), ("develop", "", "publish_snapshot"),
                  ("release/1", "", "publish_release_candidate"), ("hotfix/fix", "", "publish_hotfix_release"),
                  ("", "v1.0.0", "publish_release"), ("", "publish-fixture", "publish_feature")]
        for branch, tag, workflow in events:
            with self.subTest(workflow=workflow):
                result = self.render(CIRCLE_BRANCH=branch, CIRCLE_TAG=tag)
                self.assertEqual(list(result["workflows"]), [workflow])
                actual = result["workflows"][workflow]["jobs"]
                expected = baseline["workflows"][workflow]["jobs"]
                self.assertEqual(len(actual), len(expected))
                for before, after in zip(expected, actual):
                    self.assertEqual(list(before), list(after))
                    key = next(iter(before))
                    for contract in ("name", "requires", "context", "branch_type", "require_complete_coverage", "post-steps"):
                        self.assertEqual(before[key].get(contract), after[key].get(contract), (workflow, key, contract))
                self.assertEqual(set(result["jobs"]), set(baseline["jobs"]))
                # Actual shell commands keep every acceptance test and evidence assertion.
                for name, job in baseline["jobs"].items():
                    runs = [step["run"] for step in job["steps"] if isinstance(step, dict) and "run" in step]
                    actual_runs = [step["run"] for step in result["jobs"][name]["steps"] if isinstance(step, dict) and "run" in step]
                    self.assertEqual(runs, actual_runs, name)

    def test_core_cache_and_cold_proofs(self):
        self.write_manifest(profile="core")
        result = self.render()
        self.assertNotIn("configure-package-install", result["commands"])
        for name, job in result["jobs"].items():
            steps = job["steps"]
            self.assertNotIn("configure-package-install", steps)
            if name == "sample_bootstrap_source":
                self.assertNotIn("qqq-orb/mvn_cache_save", steps)
                self.assertFalse(any(isinstance(s, dict) and "qqq-orb/mvn_build" in s for s in steps))
            if name in ("esb_broker_conformance", "sample_acceptance", "sample_multinode_acceptance", "sample_consumer_acceptance"):
                prepared = next(s["qqq-orb/mvn_build"] for s in steps if isinstance(s, dict) and "qqq-orb/mvn_build" in s)
                self.assertFalse(prepared["compile_before_verify"])
                self.assertTrue(prepared["install_browsers"])
                last_run = max(i for i, s in enumerate(steps) if isinstance(s, dict) and "run" in s)
                self.assertGreater(steps.index("qqq-orb/mvn_cache_save"), last_run)

    def test_core_lambda_upload_and_evidence(self):
        self.write_manifest(profile="core")
        result = self.render()
        collect = result["commands"]["store-sample-results"]["steps"][0]["run"]["command"]
        self.assertIn("SampleLambdaDispatchAcceptanceTest.xml|", collect)
        self.assertIn("SampleSqsUtilityAcceptanceTest.xml) continue", collect)
        steps = result["jobs"]["sample_acceptance"]["steps"]
        self.assertIn({"store_test_results": {"path": "qqq-middleware-lambda/target/surefire-reports"}}, steps)
        self.assertIn({"store_test_results": {"path": "qqq-utility-lambdas/target/surefire-reports"}}, steps)
        self.assertIn({"persist-sample-evidence": {"shard": "sample-core"}}, steps)

    def test_core_pipeline_parameters_and_packed(self):
        self.write_manifest(profile="core")
        environment = {"QQQ_CI_MONGO_DIAGNOSTICS": "true", "QQQ_CI_NEXT_ACCEPTANCE_BUNDLE_URL": "https://example.invalid/bundle",
                       "QQQ_CI_NEXT_ACCEPTANCE_BUNDLE_SHA256": "a" * 64, "QQQ_CI_NEXT_ACCEPTANCE_RECEIPT_SHA256": "b" * 64}
        result = self.render(**environment)
        self.assertTrue(result["parameters"]["mongo_bind_diagnostics"]["default"])
        self.assertEqual(result["parameters"]["next_acceptance_bundle_sha256"]["default"], "a" * 64)
        self.assertEqual(result["parameters"]["next_acceptance_receipt_sha256"]["default"], "b" * 64)
        if PACKED:
            self.assertEqual(result, self.render(packed=True, **environment))

    def test_material_complementary_playwright_graph(self):
        self.write_manifest(profile="frontend-material")
        for branch, base in [("feature/test", "test_only"), ("develop", "publish_snapshot")]:
            for enabled in (False, True):
                with self.subTest(branch=branch, enabled=enabled):
                    result = self.render(CIRCLE_BRANCH=branch, QQQ_CI_RUN_PLAYWRIGHT=str(enabled).lower())
                    workflow = base + ("_with_playwright" if enabled else "")
                    self.assertEqual(list(result["workflows"]), [workflow])
                    jobs = result["workflows"][workflow]["jobs"]
                    self.assertEqual(len(jobs), 2 if enabled else 1)
                    maven = [j for j in jobs if next(iter(j)).startswith("qqq-orb/mvn_frontend_")]
                    self.assertEqual(len(maven), 1)
                    options = next(iter(maven[0].values()))
                    self.assertEqual(options.get("requires", []), ["playwright_tests"] if enabled else [])
                    self.assertEqual(options["node_version"], "20")
                    if PACKED:
                        self.assertEqual(result, self.render(packed=True, CIRCLE_BRANCH=branch, QQQ_CI_RUN_PLAYWRIGHT=str(enabled).lower()))

    def test_material_cache_preserves_install_and_reports(self):
        self.write_manifest(profile="frontend-material")
        result = self.render(QQQ_CI_RUN_PLAYWRIGHT="true")
        steps = result["jobs"]["playwright_tests"]["steps"]
        cache = next(s["save_cache"] for s in steps if isinstance(s, dict) and "save_cache" in s)
        self.assertEqual(cache["paths"], ["~/.npm"])
        runs = [s["run"]["command"] for s in steps if isinstance(s, dict) and "run" in s]
        self.assertEqual(runs, ["npm ci --legacy-peer-deps --prefer-offline --cache ~/.npm", "npx playwright test"])
        self.assertIn({"store_test_results": {"path": "test-results/"}}, steps)
        self.assertIn({"store_artifacts": {"path": "playwright-report/", "destination": "playwright-report"}}, steps)

    def test_frontend_release_contracts(self):
        self.git("tag", "publish-fixture")
        self.git("tag", "v1.0.0")
        self.git("tag", "v1.0.0-RC.1")
        for profile in ("frontend-core", "frontend-material"):
            self.write_manifest(profile=profile)
            for branch, tag, workflow in [("develop", "", "publish_snapshot"), ("release/1", "", "publish_release_candidate"),
                                          ("hotfix/fix", "", "publish_hotfix_release"), ("", "publish-fixture", "publish_feature"),
                                          ("", "v1.0.0", "publish_release")]:
                result = self.render(CIRCLE_BRANCH=branch, CIRCLE_TAG=tag)
                self.assertEqual(list(result["workflows"]), [workflow])
                options = next(iter(result["workflows"][workflow]["jobs"][0].values()))
                if profile == "frontend-core":
                    self.assertTrue(options["npm_trusted_publishing"])
                    self.assertEqual(options["node_version"], "24.21")
                    self.assertEqual(options["context"], ["qqq-maven-registry-credentials", "build-qqq-sample-app"])
                else:
                    self.assertEqual(options["context"], ["qqq-maven-registry-credentials"])
            main = self.render(CIRCLE_BRANCH="main")
            self.assertEqual(list(main["workflows"]), ["publish_release" if profile == "frontend-core" else "test_only"])
            rc_tag = self.render(CIRCLE_BRANCH="", CIRCLE_TAG="v1.0.0-RC.1")
            self.assertEqual(list(rc_tag["workflows"]), ["publish_release" if profile == "frontend-core" else "test_only"])

    def test_profile_specific_options_rejected(self):
        for profile, options in [("qbit", {"node_version": "22"}), ("frontend-core", {"browsers": False}),
                                 ("frontend-material", {"api_checks": True}), ("frontend-core", {"publish": {"asciidoc": True}})]:
            self.write_manifest(profile=profile, **options)
            self.render(ok=False)

    def test_cli_publication_is_opt_in_and_context_bound(self):
        self.write_manifest(profile="cli", default_branch="main")
        self.git("tag", "v1.0.0-RC.1")
        result = self.render(CIRCLE_TAG="v1.0.0-RC.1")
        self.assertEqual(list(result["workflows"]), ["test_only"])
        options = result["workflows"]["test_only"]["jobs"][0]["qqq-orb/cli_verify_publish"]
        self.assertFalse(options["publish"])
        self.assertNotIn("context", options)
        self.write_manifest(profile="cli", default_branch="main", publish={"release": True})
        self.render(ok=False)
        self.write_manifest(profile="cli", default_branch="main", publish={"release": True}, publish_context="verified-packages")
        result = self.render(CIRCLE_TAG="v1.0.0-RC.1")
        options = result["workflows"]["publish_release"]["jobs"][0]["qqq-orb/cli_verify_publish"]
        self.assertTrue(options["publish"])
        self.assertEqual(options["context"], ["verified-packages"])
        self.change_docs()
        self.assertEqual(list(self.render(CIRCLE_TAG="v1.0.0-RC.1")["workflows"]), ["test_only"])
        self.assertEqual(list(self.render(CIRCLE_BRANCH="main")["workflows"]), ["test_only"])
        if PACKED:
            self.assertEqual(self.render(), self.render(packed=True))

    def test_voyage_owns_complete_template(self):
        self.write_manifest(profile="voyage")
        result = self.render(CIRCLE_BRANCH="release/1")
        self.assertEqual(len(result["jobs"]), 9)
        self.assertEqual(len(result["workflows"]), 3)
        self.assertNotIn("__ORB_VERSION__", json.dumps(result))
        self.assertEqual(result["orbs"]["qqq-orb"], "kingsrook/qqq-orb@0.7.0")
        if PACKED:
            self.assertEqual(result, self.render(packed=True, CIRCLE_BRANCH="release/1"))

    def test_specialist_profiles_source_and_packed_parity(self):
        for profile, workflow in (("android", "test-and-build"), ("mcp-policy", "validate"),
                                  ("all", "verify-and-smoke"), ("app-starter", "test_only"),
                                  ("frontend-next", "publish_release")):
            with self.subTest(profile=profile):
                self.write_manifest(profile=profile)
                result = self.render(CIRCLE_BRANCH="main")
                self.assertIn(workflow, result["workflows"])
                self.assertNotIn("__ORB_VERSION__", json.dumps(result))
                if PACKED:
                    self.assertEqual(result, self.render(packed=True, CIRCLE_BRANCH="main"))

    def test_marketing_source_and_packed_parity(self):
        self.write_manifest(profile="marketing", default_branch="main")
        result = self.render(CIRCLE_BRANCH="main")
        self.assertEqual(result, pipeline.MARKETING_TEMPLATE)
        if PACKED:
            self.assertEqual(result, self.render(packed=True, CIRCLE_BRANCH="main"))

    def test_qbit_publication_policy_packed_parity(self):
        self.write_manifest(release_on_main=True, release_tag_policy="v-prefix",
                            test_branch_policy="feature")
        self.git("tag", "v1.2.3-RC.1")
        for environment in ({"CIRCLE_BRANCH": "main"},
                            {"CIRCLE_TAG": "v1.2.3-RC.1", "CIRCLE_BRANCH": ""},
                            {"CIRCLE_BRANCH": "integration-example"}):
            result = self.render(**environment)
            if environment.get("CIRCLE_BRANCH") != "integration-example":
                self.assertIn("publish_release", result["workflows"])
            if PACKED:
                self.assertEqual(result, self.render(packed=True, **environment))

    @unittest.skipUnless(PACKED, "pass --packed to verify the shipped orb resource")
    def test_packed_full_profile(self):
        self.assertEqual(self.render(), self.render(packed=True))
        self.assertEqual(self.render(CIRCLE_BRANCH="develop"), self.render(packed=True, CIRCLE_BRANCH="develop"))


if __name__ == "__main__":
    unittest.main()
